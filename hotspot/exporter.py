import copy
import os
import shutil
import tempfile
from pathlib import Path
from .common import canonical, digest, now, require, write, read, sha, contained
from .review import gate, manifest
from .store import DIRS

WORKFLOW='history_long_video'

def export_candidate(store, identity, target_workflow, actor, authorize=False):
    require(target_workflow==WORKFLOW,'目标工作流不在允许范围')
    require(authorize is True and isinstance(actor,str) and bool(actor.strip()), '请明确选择此版本并授权导入目标选题库')
    status=gate(store,identity,production=True)
    require(status['eligible'],'导出阻断：'+'；'.join(status['errors']))
    c=store.get('candidate',identity); v=c['candidate_version']
    key=digest([identity,v,target_workflow]); receipt_id='RECEIPT-'+key[:24]
    folder=store.root/DIRS[4]/key
    inbox=store.project/'01_选题库/热点导入库'/key
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT body FROM receipts WHERE key=?',(key,)).fetchone()
        if prior:
            import json
            r=json.loads(prior['body']); verify_bundle(folder); verify_bundle(inbox)
            require(read(folder/'candidate.json')['review']['reviewed_input_hash']==status['input_hash'],'该版本已导出后依赖变化；请修订候选版本')
            return r
        reviewed=copy.deepcopy(c)
        reviewed['state']='exported'
        reviewed['review']={'status':'approved','reviewer_id':status['review']['reviewer_id'],'reviewed_candidate_version':v,'reviewed_input_hash':status['input_hash'],'reviewed_at':status['review']['reviewed_at'],'open_fact_blockers':0,'independence_record':status['review']['independence_record']}
        reviewed['export']={'eligible':True,'target_workflow':target_workflow,'receipt_id':receipt_id,'episode_id':None,'exported_at':now()}
        if folder.exists():
            verify_bundle(folder)
            require(read(folder/'candidate.json')['review']['reviewed_input_hash']==status['input_hash'],'恢复发现同版本内容变化；须新版本导出')
        else:
            stage=Path(tempfile.mkdtemp(prefix='.pending-',dir=folder.parent))
            try:
                write(stage/'candidate.json',reviewed)
                write(stage/'review.json',status['review'])
                write(stage/'input-manifest.json',manifest(store,c))
                write(stage/'authorization.json',{'actor':actor,'candidate_id':identity,'version':v,'workflow':target_workflow,'at':now(),'scope':'只进入待立项选题库，不创建剧集、不触发制作或发布'})
                for ref in c['snapshot_refs']:
                    s=store.get('snapshot',ref['snapshot_id'])
                    write(stage/'snapshots'/(digest(s)+'.json'),s)
                    p=store.verify_file(s['raw']); dest=stage/'raw'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
                for e in c['evidence']:
                    asset=store.get('evidence_asset',e['evidence_id']); p=store.verify_file(asset['raw']);dest=stage/'evidence'/p.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest)
                (stage/'热点关联卡.md').write_text(f"# {c['proposed_title']}\n\n{c['bridge_claim']}\n\n故事问题：{c['story_question']}\n\n关联类型：{c['relation_type']}\n\n预计时长：{c['estimated_minutes']}分钟（估计）\n\n{c['duration_basis']}\n\n采用版本：{identity} / {v}\n\n完整证据和反证见同包 candidate.json、evidence 及 input-manifest.json。\n\n状态：待用户选题立项，写稿前仍需既有故事线查重、资料与提纲审核。\n",encoding='utf-8')
                files={str(p.relative_to(stage)):sha(p.read_bytes()) for p in stage.rglob('*') if p.is_file()}
                write(stage/'bundle-manifest.json',files)
                os.replace(stage,folder)
            finally:
                if stage.exists():shutil.rmtree(stage)
        inbox.parent.mkdir(parents=True,exist_ok=True)
        if inbox.exists():
            verify_bundle(inbox)
            require(read(inbox/'bundle-manifest.json')==read(folder/'bundle-manifest.json'),'目标导入包与原导出内容不一致')
        else:
            stage=Path(tempfile.mkdtemp(prefix='.pending-',dir=inbox.parent))
            try:
                shutil.copytree(folder,stage,dirs_exist_ok=True);os.replace(stage,inbox)
            finally:
                if stage.exists():shutil.rmtree(stage)
        receipt={'receipt_id':receipt_id,'candidate_id':identity,'candidate_version':v,'target_workflow':target_workflow,'bundle':str(folder),'inbox':str(inbox),'episode_id':None,'status':'IMPORTED_AWAITING_TOPIC_SELECTION','at':now()}
        db.execute('INSERT INTO receipts VALUES(?,?)',(key,canonical(receipt).decode()))
    store.event('exported',receipt)
    return receipt

def verify_bundle(folder):
    folder=Path(folder)
    for path,expected in read(folder/'bundle-manifest.json').items():
        p=contained(folder,path);require(p.is_file() and sha(p.read_bytes())==expected,'交接包哈希不匹配：'+path)
    return True

def audit(store):
    faults=[]
    for kind in ('snapshot','evidence_asset'):
        for item in store.all(kind):
            if item.get('raw'):
                try:store.verify_file(item['raw'])
                except ValueError as exc:
                    identity=item['snapshot_id'] if kind=='snapshot' else item['evidence_id']
                    store.invalidate(kind,identity,str(exc));faults.append({'kind':kind,'id':identity,'error':str(exc)})
    affected=[]
    with store.db() as db:
        import json
        receipts=[json.loads(r['body']) for r in db.execute('SELECT body FROM receipts')]
    for receipt in receipts:
        status=gate(store,receipt['candidate_id'],production=True)
        reasons=list(status['errors'])
        if receipt['candidate_version']!=status['candidate_version']:reasons.append('候选有新版本')
        for key in ('bundle','inbox'):
            try:verify_bundle(receipt[key])
            except (ValueError,OSError) as exc:reasons.append(str(exc))
        if reasons:
            notice={'receipt_id':receipt['receipt_id'],'state':'needs_recheck','reasons':reasons,'at':now()}
            write(store.root/DIRS[4]/'复审通知'/(receipt['receipt_id']+'.json'),notice)
            affected.append(notice)
    result={'at':now(),'faults':faults,'affected_exports':affected}
    store.event('integrity_audit',result)
    return result
