import fcntl
from contextlib import contextmanager
from .store import Store
from .common import require, read, now
from . import acquisition, review, exporter

@contextmanager
def exclusive(store):
    with (store.root/'.writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

def overview(store):
    snapshots=store.all('snapshot');candidates=[]
    for c in store.all('candidate'):
        candidates.append({'candidate':c,'gate':review.gate(store,c['candidate_id'])})
    return {'environment':store.environment,'project':str(store.project),'automatic_collection':'NOT_CONFIGURED','model':'NOT_CONFIGURED','retrieval':'LOCAL_KEYWORD_ONLY','production_acceptance':'NOT_RUN',
        'classifications':store.all('classification'),'snapshots':snapshots,'candidates':candidates,'evidence':store.all('evidence_asset'),'events':store.events(),
        'recommendations':sorted([x for x in candidates if x['gate']['eligible']],key=lambda x:x['candidate']['editorial_score'] if x['candidate']['editorial_score'] is not None else -1,reverse=True)[:5],
        'rules':{'duration_minutes':review.policy(store)['duration_minutes'],'basis':'现有工作台最新内容选题偏好；覆盖交接包旧15–40分钟初值','publishing':False}}

def dispatch(store,action,data):
    with exclusive(store):
        if action=='manual':return acquisition.import_manual(store,data)
        if action=='collect':return acquisition.collect(store)
        if action=='replay':return acquisition.replay(store,data['snapshot_id'])
        if action=='create_candidate':return review.create_candidate(store,data['snapshot_id'],data['record_id'],data['author'])
        if action=='save_candidate':return review.save_candidate(store,data['candidate'],data['author'])
        if action=='evidence':return review.register_evidence(store,data)
        if action=='search':return review.search_evidence(store,data['query'])
        if action=='review_packet':return review.review_packet(store,data['candidate_id'])
        if action=='review':return review.submit_review(store,data['candidate_id'],data)
        if action=='gate':return review.gate(store,data['candidate_id'],production=True)
        if action=='export':return exporter.export_candidate(store,data['candidate_id'],data['target_workflow'],data['actor'],data.get('authorize',False))
        if action=='invalidate':
            require(data['kind'] in ('snapshot','evidence_asset','candidate'),'不可撤回的类别')
            require(isinstance(data.get('reason'),str) and data['reason'].strip(),'需记录更正或撤回原因')
            store.get(data['kind'],data['id']); store.invalidate(data['kind'],data['id'],data['reason']);return exporter.audit(store)
        if action=='audit':return exporter.audit(store)
        if action=='overview':return overview(store)
        raise ValueError('未知操作')
