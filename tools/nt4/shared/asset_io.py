"""Read Fallout 4 BA2/plugin/NIF data without mutating the installed build."""
from pathlib import Path
import struct,zlib,re

def norm(path):return path.replace('\\','/').strip('\0').lower().lstrip('/')

class Reader:
    def __init__(self,data):self.data=data;self.pos=0
    def take(self,n):
        assert 0<=n<=len(self.data)-self.pos,(self.pos,n,len(self.data))
        b=self.data[self.pos:self.pos+n];self.pos+=n;return b
    def unpack(self,fmt):
        n=struct.calcsize('<'+fmt);return struct.unpack('<'+fmt,self.take(n))
    def one(self,fmt):return self.unpack(fmt)[0]
    def string(self,short=False):return self.take(self.one('B' if short else 'I')).rstrip(b'\0').decode(errors='replace')

class BA2:
    def __init__(self,path):
        self.path=Path(path);self.entries={}
        with self.path.open('rb') as f:
            magic,version,self.kind,count,names_offset=struct.unpack('<4sI4sIQ',f.read(24))
            assert magic==b'BTDX' and version==1,(str(path),magic,version)
            entries=[]
            for _ in range(count):
                if self.kind==b'GNRL':entries.append(struct.unpack('<I4sIIQIII',f.read(36)))
                elif self.kind==b'DX10':
                    h=struct.unpack('<I4sIBBHHHBBH',f.read(24))
                    chunks=[struct.unpack('<QIIHHI',f.read(24)) for _ in range(h[4])]
                    entries.append((h,chunks))
                else:raise ValueError(self.kind)
            f.seek(names_offset)
            for entry in entries:
                name=f.read(struct.unpack('<H',f.read(2))[0]).decode(errors='replace')
                self.entries[norm(name)]=entry
    def read(self,name):
        entry=self.entries[norm(name)]
        def payload(f,offset,packed,unpacked):
            f.seek(offset);b=f.read(packed or unpacked);b=zlib.decompress(b) if packed else b
            assert len(b)==unpacked,(self.path,name,len(b),unpacked)
            return b
        with self.path.open('rb') as f:
            if self.kind==b'GNRL':return payload(f,entry[4],entry[5],entry[6])
            h,chunks=entry;height,width,mips,fmt,flags=h[6],h[7],h[8],h[9],h[10]
            block=8 if fmt in {71,72,80,81} else 16
            size=max(1,(width+3)//4)*max(1,(height+3)//4)*block
            dds=[124,0xA1007,height,width,size,0,mips]+[0]*11
            dds += [32,4,int.from_bytes(b'DX10','little'),0,0,0,0,0]
            cube=bool(flags&0x800)
            dds += [0x401008 if mips>1 else 0x1000,0xFE00 if cube else 0,0,0,0]
            assert len(dds)==31
            header=b'DDS '+struct.pack('<31I',*dds)+struct.pack('<5I',fmt,3,4 if cube else 0,1,0)
            return header+b''.join(payload(f,c[0],c[1],c[2]) for c in sorted(chunks,key=lambda c:c[3]))

def subrecords(data):
    r=Reader(data);extended=None
    while r.pos<len(data):
        sig,size=r.unpack('4sH')
        if sig==b'XXXX':assert size==4;extended=r.one('I');continue
        if extended is not None:size,extended=extended,None
        yield sig.decode(),r.take(size)

def plugin_records(path,wanted):
    masters=[]
    with Path(path).open('rb') as f:
        end=Path(path).stat().st_size
        while f.tell()<end:
            h=f.read(24);assert len(h)==24
            sig,size,flags,fid=struct.unpack_from('<4sIII',h)
            if sig==b'GRUP':continue
            if sig!=b'TES4' and sig.decode() not in wanted:f.seek(size,1);continue
            data=f.read(size)
            if flags&0x40000:data=zlib.decompress(data[4:])
            fields=list(subrecords(data))
            if sig==b'TES4':masters=[b.rstrip(b'\0').decode() for t,b in fields if t=='MAST'];continue
            def key(value):
                i=value>>24
                if i>len(masters):return 'unresolved:'+Path(path).name.lower()+':'+f'{value:08X}'
                return (masters[i] if i<len(masters) else Path(path).name).lower()+':'+f'{value&0xFFFFFF:06X}'
            yield {'sig':sig.decode(),'key':key(fid),'flags':flags,'fields':fields,'masters':masters[:],
                   'plugin':Path(path).name,'local_id':fid}

def nif_header(data):
    r=Reader(data);r.pos=data.index(b'\n')+1
    version=r.one('I');endian=r.one('B');user,nb,bs=r.unpack('III')
    assert version==0x14020007 and endian==1 and user==12 and bs==130,(version,user,bs)
    author=r.string(True);process=r.string(True);export=r.string(True);maxpath=r.string(True)
    nt=r.one('H');types=[r.string() for _ in range(nt)]
    indexes=r.unpack('H'*nb);sizes=r.unpack('I'*nb)
    ns,maxlen=r.unpack('II');strings=[r.string() for _ in range(ns)]
    groups=r.one('I');r.take(groups*4)
    blocks=[]
    for i,(index,size) in enumerate(zip(indexes,sizes)):
        offset=r.pos;blocks.append({'id':i,'type':types[index&0x7FFF],'offset':offset,'data':r.take(size)})
    return {'version':version,'bs_version':bs,'strings':strings,'blocks':blocks,'footer':data[r.pos:]}

def embedded_paths(data,extensions):
    # NIF/BGSM filenames are length-prefixed. Check lengths rather than treating
    # arbitrary floats/geometry bytes as a filename.
    pattern=rb'[^\x00-\x1f\x7f-\xff]{2,350}\.(?:'+b'|'.join(e.encode() for e in extensions)+rb')\x00?'
    result=set()
    for m in re.finditer(pattern,data,re.I):
        # Search for the u32 prefix within the longest printable span.
        for start in range(m.start(),m.end()-4):
            n=m.end()-start
            if start>=4 and struct.unpack_from('<I',data,start-4)[0]==n:
                result.add(norm(data[start:m.end()].decode()));break
            if start>=4 and data[m.end()-1:m.end()]==b'\0' and struct.unpack_from('<I',data,start-4)[0]==n-1:
                result.add(norm(data[start:m.end()-1].decode()));break
    return sorted(result)
