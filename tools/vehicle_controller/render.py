"""Offline pure-C take replay, with native dry stem exports."""
import ctypes as C
from pathlib import Path
import struct
import json
from .native import Engine
from . import take,dna_bank


class FloatWav:
    def __init__(self,path,channels):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.path.open('wb');self.channels=channels;self.size=0
        self.stream.write(bytes(44))

    def write(self,data):self.stream.write(data);self.size+=len(data)

    def close(self):
        if not self.stream.closed:
            self.stream.seek(0);self.stream.write(struct.pack('<4sI4s4sIHHIIHH4sI',b'RIFF',36+self.size,b'WAVE',b'fmt ',16,
                3,self.channels,48000,48000*self.channels*4,self.channels*4,32,b'data',self.size));self.stream.close()


def export(bridge,value,prefix,stems=True):
    paths=[];writers=[];prefix=Path(prefix);source_events=[]
    try:
        monitor=FloatWav(str(prefix)+'_mix.wav',2);writers.append(monitor);paths.append(str(monitor.path))
        for row in bridge.stems if stems else []:
            writer=FloatWav(str(prefix)+'_'+row['name']+'.wav',row['channels']);writers.append(writer);paths.append(str(writer.path))
        with Engine(bridge,value['catalog']['id'],value['event_overrides'],value['startup_response'],value.get('event_policy'),value.get('dna_bank')) as engine:
            engine.set(value['initial']);index=0;events=value['events'];width=bridge.channels()
            while engine.frame<value['frames']:
                while index<len(events) and events[index]['frame']==engine.frame:engine.set(events[index]['control']);index+=1
                end=min(engine.frame+480,value['frames'],events[index]['frame'] if index<len(events) else value['frames'])
                frames=end-engine.frame
                if frames<=0:raise ValueError('行程事件时序无效')
                monitor.write(engine.process(frames));source_events.extend(engine.last_events);offset=0
                for row,writer in zip(bridge.stems,writers[1:]):
                    values=(C.c_float*(frames*row['channels']))()
                    for n in range(frames):
                        for ch in range(row['channels']):values[n*row['channels']+ch]=engine.stems[n*width+offset+ch]
                    writer.write(bytes(values));offset+=row['channels']
            state=engine.state()
        event_path=Path(str(prefix)+'_events.json')
        source_events=[event for event in source_events if event['frame']<value['frames'] or event['action']==2 and event['frame']==value['frames']]
        event_path.write_text(json.dumps(dict(schema='vsl.source-event-stream/1',sample_rate=48000,
            frames=value['frames'],stream_id=value['stream_id'],event_bank_sha256=bridge.event_bank_sha256,
            event_effective_sha256=value['event_effective_sha256'],stem_layout=bridge.stems,
            source_effective_sha256=value['source_effective_sha256'],startup_response=value['startup_response'],
            catalog_assets_sha256=value.get('catalog_assets_sha256'),catalog_assets=value.get('catalog_assets'),
            event_policy=value.get('event_policy'),
            dna_bank_sha256=dna_bank.digest(value.get('dna_bank')),
            events=source_events,note='Event slots are reused; pair slot with instance ID and half-open frame lifetime.'),ensure_ascii=False,indent=2),encoding='utf-8')
        paths.append(str(event_path))
        return dict(paths=paths,frames=value['frames'],final_state=state,source_events=source_events)
    finally:
        for writer in writers:writer.close()
