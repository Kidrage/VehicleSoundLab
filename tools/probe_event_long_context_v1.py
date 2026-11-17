"""Record the already explored fixed 200 ms windows on the same six B candidates."""
import argparse
from pathlib import Path
import shutil
import soundfile as sf
from event_authoring.audio import read
from event_authoring.context import probe
from research_archive_v1 import load,save,sha


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=False)
    repo=Path(__file__).resolve().parents[1];root=Path('E:/VehicleSoundLab/references/analysis/short_event_scan_v1')
    scan=load(root/'B-scan1/report.json');selection=load(root/'B-fits2/report.json')['selection']
    source=Path(scan['source']);assert sha(source)==scan['source_sha256']
    shutil.copy2(__file__,out/'executed_probe.py');rows=[]
    for selected in selection:
        peak=selected['source_seconds'];folder=out/('rank'+str(selected['rank']));folder.mkdir()
        event=[peak-.020,peak+.180];backgrounds=dict(before=[peak-.300,peak-.200],after=[peak+.200,peak+.300])
        report,_=probe(source,event,backgrounds)
        contrasts={r['name']:r['full_contrast_db'] for r in report['backgrounds']}
        qualified=all(v>=3 for v in contrasts.values())
        report.update(peak_seconds=peak,event_seconds=event,background_seconds=backgrounds,
            both_backgrounds_above_3db=qualified,exploratory_not_predeclared=True,
            physical_afterfire_confirmed=False)
        for name,pair in [('event',event),*backgrounds.items()]:
            x,rate,origin=read(source,*pair);sf.write(folder/(name+'.wav'),x,rate,subtype='FLOAT')
        save(folder/'report.json',report)
        rows.append(dict(rank=selected['rank'],peak_seconds=peak,contrasts_db=contrasts,qualified=qualified,
                         report_sha256=sha(folder/'report.json')))
    assert len(rows)==6 and not any(r['qualified'] for r in rows)
    save(out/'report.json',dict(result='passed',question='Does a fixed200ms event retain both3dB contrasts?',
        answer=False,exploratory_not_predeclared=True,source=str(source),source_sha256=sha(source),cases=rows,
        limits='Exploration happened before ensemble plan; recorded now with exact evidence. No alternate-window search or physical afterfire classification.',
        goal_complete=False,timbre_accepted=False))
    print(rows,flush=True)


if __name__=='__main__':main()
