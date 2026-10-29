import copy
from .common import BASE, read, validate, require, digest, now, safe_url, redact
from .store import uid

RULES='evidence-gate/1.0.0'

def policy(store):
    path=store.project/'00_项目配置/内容选题偏好.json'
    config=read(path) if path.exists() else {'duration_minutes':[15,60]}
    bounds=config.get('duration_minutes',[15,60])
    require(isinstance(bounds,list) and len(bounds)==2 and all(type(x) in (int,float) for x in bounds) and 0<bounds[0]<=bounds[1], '现有时长配置无效')
    return {'duration_minutes':bounds,'config_hash':digest(config)}

def create_candidate(store, snapshot_id, record_id, author):
    require(isinstance(author,str) and author.strip(),'需填写作者身份')
    snapshot=store.get('snapshot',snapshot_id)
    require(snapshot['quality_gate']!='quarantined','隔离快照不能创建候选')
    related=[c for c in store.all('candidate') if any(ref['snapshot_id']==snapshot_id and ref['record_id']==record_id for ref in c['snapshot_refs'])]
    require(len(related)<3,'每热点最多3个切口；请修订现有候选')
    record=next((r for r in snapshot['records'] if r['record_id']==record_id),None)
    require(record,'热点条目不存在')
    c=read(BASE/'examples/candidate.template.json')
    c.update(candidate_id=uid('TOPIC'),candidate_version=1,environment=store.environment,is_fixture=snapshot['is_fixture'],
        snapshot_refs=[{'snapshot_id':snapshot_id,'record_id':record_id}],entities=[],bridge_claim='待检索：'+record['title_raw'],proposed_title=record['title_raw'])
    c['timeliness']['reason']='尚未复核热点语境；不推测有效期'
    return save_candidate(store,c,author)

def save_candidate(store, data, author):
    require(isinstance(author,str) and bool(author.strip()),'作者身份不能为空')
    c=copy.deepcopy(data)
    # External files never supply authoritative review or export state.
    c['state']='evidence_pending'
    c['review']={'status':'not_started','reviewer_id':None,'reviewed_candidate_version':None,'reviewed_input_hash':None,'reviewed_at':None,'open_fact_blockers':None,'independence_record':None}
    c['export']={'eligible':False,'target_workflow':None,'receipt_id':None,'episode_id':None,'exported_at':None}
    validate('candidate',c)
    require(c['environment']==store.environment, '候选与运行环境不一致')
    for e in c['evidence']:
        if e['url']: require(safe_url(e['url'])==e['url'],'证据链接包含秘密字段或非安全协议')
    for ref in c['snapshot_refs']:
        s=store.get('snapshot',ref['snapshot_id'])
        require(s['is_fixture']==c['is_fixture'] and s['environment']==c['environment'],'快照与候选环境/样例标记不一致')
        require(any(r['record_id']==ref['record_id'] for r in s['records']),'热点引用不存在')
    existing=[x for x in store.all('candidate') if x['candidate_id']==c['candidate_id']]
    if existing:
        require(c['candidate_version']==existing[0]['candidate_version']+1,'修订版本必须递增1')
    else: require(c['candidate_version']==1,'首版必须为1')
    from .common import canonical
    # Candidate and author commit together; a restart cannot leave an orphan version.
    with store.db() as db:
        for kind, obj in [('candidate',c), ('author',{'actor':author.strip()})]:
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?)', (kind,c['candidate_id'],c['candidate_version'],canonical(obj).decode(),digest(obj)))
    if existing:store.event('candidate_revised',{'candidate_id':c['candidate_id'],'version':c['candidate_version'],'downstream':'needs_recheck'})
    return c

def register_evidence(store, data):
    require(all(isinstance(data.get(k),str) and data[k].strip() for k in ('evidence_id','text','source_family_id','title','recorded_by')), '证据需编号、实际正文、来源家族、标题和记录人')
    require(type(data.get('version')) is int and data['version']>0,'证据版本必须为正整数')
    existing=[e for e in store.all('evidence_asset') if e['evidence_id']==data['evidence_id']]
    require(data['version']==(existing[0]['version']+1 if existing else 1),'证据版本必须连续递增')
    asset={k:data[k] for k in ('evidence_id','version','source_family_id','title','recorded_by')}
    asset.update(at=now(),url=safe_url(data.get('url')),raw=store.archive({'text':redact(data['text'])},'02_历史关联候选/证据'))
    store.put('evidence_asset',asset['evidence_id'],asset,asset['version'])
    store.event('evidence_registered',{'id':asset['evidence_id'],'version':asset['version'],'prior_dependents_need_recheck':bool(existing)})
    return asset

def search_evidence(store, query):
    terms=query.strip().split()
    require(bool(terms),'请输入检索关键词')
    hits=[]
    for asset in store.all('evidence_asset'):
        text=read(store.verify_file(asset['raw']))['text']
        if all(term in text or term in asset['title'] for term in terms):
            index=max(0,text.find(terms[0])); hits.append({'evidence_id':asset['evidence_id'],'version':asset['version'],'title':asset['title'],'source_family_id':asset['source_family_id'],'excerpt':text[max(0,index-80):index+400], 'status':'检索命中，尚不证明命题支持'})
    return {'query':query,'hits':hits,'provider':'local-keyword/1.0.0','remote_retrieval':'NOT_CONFIGURED'}

def manifest(store,c):
    snapshots=[]; evidence=[]
    for ref in c['snapshot_refs']:
        s=store.get('snapshot',ref['snapshot_id'])
        require(not store.invalid('snapshot',s['snapshot_id']),'快照已撤回或更正')
        require(s['quality_gate']!='quarantined','快照处于隔离状态')
        require(s['raw'] is not None,'快照无原文')
        store.verify_file(s['raw'])
        require(any(r['record_id']==ref['record_id'] for r in s['records']),'热点引用不存在')
        snapshots.append({'reference':ref,'snapshot_hash':digest(s),'raw_hash':s['raw']['sha256']})
    for e in c['evidence']:
        a=store.get('evidence_asset',e['evidence_id'])
        require(not store.invalid('evidence_asset',e['evidence_id']),'证据已撤回')
        store.verify_file(a['raw'])
        require(a['source_family_id']==e['source_family_id'] and a['title']==e['title'] and a['url']==e['url'],'证据元数据与归档不一致')
        evidence.append(a)
    content={k:v for k,v in c.items() if k not in ('review','export','state','editorial_score')}
    return {'candidate':content,'snapshots':snapshots,'evidence_assets':evidence,'rules_version':RULES,'prompt_version':None,'model_id':None,'project_policy':policy(store)}

def content_errors(store,c):
    errors=[]
    def check(ok,msg):
        if not ok:errors.append(msg)
    claims={x['claim_id']:x for x in c['claims']}; evid={x['evidence_id']:x for x in c['evidence']}
    check(len(claims)==len(c['claims']), '主张ID重复')
    check(len(evid)==len(c['evidence']), '证据ID重复')
    check(len({e['entity_id'] for e in c['entities']})==len(c['entities']), '实体ID重复')
    relation=[x for x in c['claims'] if x['domain']=='relation']
    check(len(relation)==1 and relation[0]['claim_id']==c['bridge_claim_id'] and relation[0]['text']==c['bridge_claim'] and relation[0]['critical'], '需要唯一且关键的主要桥接命题，文字与ID须一致')
    check(c['relation_type'] in ('direct','analogy'),'弱关联或无关联不推荐')
    check(c['modern_context_status'] in ('verified','context_not_required'),'现代事件前提未确认')
    if c['modern_context_status']=='verified':
        check(any(x['domain']=='modern_context' and x['critical'] for x in c['claims']), '事件确认需要关键现代事实命题')
    check(bool(c['entities']),'实体尚未枚举')
    for e in c['entities']:
        check(e['resolution'] in ('resolved','not_required'), '实体待消歧：'+e['mention'])
        if e['resolution']=='resolved':check(bool(e['selected_identity']) and bool(e['support_evidence_ids']),'已消歧实体缺少身份或依据')
        check(all(x in evid for x in e['support_evidence_ids']),'实体引用缺失')
    pairs=set()
    for link in c['evidence_links']:
        pair=(link['evidence_id'],link['claim_id']);check(pair not in pairs,'重复命题证据关系'); pairs.add(pair)
        check(link['claim_id'] in claims and link['evidence_id'] in evid,'证据关系引用缺失')
        if link['support_verdict']!='not_checked':
            check(all(link.get(k) for k in ('location','checked_excerpt','checked_by','checked_at')),'核对记录不完整')
            if link['evidence_id'] in evid:
                try:
                    asset=store.get('evidence_asset',link['evidence_id']);text=read(store.verify_file(asset['raw']))['text']
                    check(bool(link['checked_excerpt']) and link['checked_excerpt'] in text,'核对摘录不在实际归档正文中')
                except (ValueError,OSError) as exc: errors.append(str(exc))
    for claim in c['claims']:
        check(all(x in evid for x in claim['evidence_ids']+claim['counterevidence_ids']),'主张证据引用缺失')
        links=[l for l in c['evidence_links'] if l['claim_id']==claim['claim_id']]
        check(all(any(l['evidence_id']==eid and l['support_verdict']=='contradicts' for l in links) for eid in claim['counterevidence_ids']),'反证未逐项核对')
        if claim['critical']:
            check(claim['status'] in ('supported','qualified'),'关键主张未得到支持：'+claim['claim_id'])
            support=[l for l in links if l['support_verdict'] in ('supports','partly_supports') and l['evidence_id'] in claim['evidence_ids'] and evid.get(l['evidence_id'],{}).get('access_status')=='read']
            check(bool(support),'关键主张缺实际核对支持：'+claim['claim_id'])
            if claim['status']=='qualified' or any(l['support_verdict'] in ('partly_supports','contradicts') for l in links):
                check(bool(claim['allowed_wording']),'部分支持或反证需要限定措辞')
    for issue in c['issues']:
        check(all(e in evid for e in issue['evidence_ids']),'问题单证据引用缺失')
        if issue['severity']=='P0' or issue['is_factual']:
            check(issue['status']=='rechecked','事实/P0问题必须修复并复审')
        elif issue['severity']=='P1':check(issue['status']=='rechecked','P1须复审；本版不提供豁免快捷通道')
        elif issue['severity']=='P2':check(issue['status']=='rechecked','P2需复审；保留理由由审核记录填写')
        if issue['revision_round']>=2 and issue['status']!='rechecked':errors.append('两轮返修仍未通过，等待人工处理：'+issue['issue_id'])
    bounds=policy(store)['duration_minutes']
    check(c['estimated_minutes'] is not None and bounds[0]<=c['estimated_minutes']<=bounds[1] and bool(c['duration_basis']), f'需有资料依据的{bounds[0]}–{bounds[1]}分钟制作估计')
    check(bool(c['timeliness']['reviewed_at']) and bool(c['timeliness']['reason']),'缺时效复核记录')
    return errors

def review_packet(store, identity):
    c=store.get('candidate',identity)
    m=manifest(store,c)
    return {'candidate_id':identity,'candidate_version':c['candidate_version'],'input_hash':digest(m),'inputs':m,'checks':content_errors(store,c), 'instruction':'逐条核对来源、实体、现代前提、支持范围、反证和时效。作者自评分不提供给审核者。'}

def submit_review(store, identity, data):
    c=store.get('candidate',identity); packet=review_packet(store,identity)
    author=store.get('author',identity,c['candidate_version'])['actor']
    require(data.get('reviewer_id') and data['reviewer_id'].strip()!=author,'审核者须独立于本版作者')
    require(data.get('reviewer_type')=='human','本版仅接收人工审核，模型审核未配置')
    require(data.get('independence_record') and data.get('notes'),'需保存独立审核方式和核对结论')
    require(data.get('input_hash')==packet['input_hash'] and data.get('candidate_version')==c['candidate_version'],'审核输入已变化，请重新读取审核包')
    require(data.get('decision') in ('approved','hold','rejected'),'审核结论无效')
    if data['decision']=='approved':
        require(not packet['checks'],'审核阻断：'+'；'.join(packet['checks']))
        require(data.get('attest_checked') is True,'必须明确确认已实际核对原文与反证')
        require(set(data.get('checked_claim_ids',[]))=={x['claim_id'] for x in c['claims'] if x['critical']},'审核需覆盖全部关键主张')
    review={**data,'reviewed_at':now(),'review_id':uid('REVIEW')}
    store.put('review',review['review_id'],{'candidate_id':identity,**review})
    store.event('review_recorded',{'candidate_id':identity,'review_id':review['review_id'],'decision':data['decision']})
    return review

def current_review(store,c):
    return next((r for r in store.all('review') if r['candidate_id']==c['candidate_id'] and r['candidate_version']==c['candidate_version']),None)

def gate(store,identity, production=False):
    c=store.get('candidate',identity); errors=content_errors(store,c)
    if production and (c['environment']!='production' or c['is_fixture']):errors.append('测试/构造卡禁止生产导出')
    if store.invalid('candidate',identity): errors.append('候选已撤回，需人工处理')
    review=current_review(store,c)
    try: hash_value=digest(manifest(store,c))
    except (ValueError,OSError) as exc:errors.append(str(exc));hash_value=None
    if not review or review['decision']!='approved':errors.append('缺少当前版本的独立通过记录')
    elif review['input_hash']!=hash_value:errors.append('审核输入已变化，待复审')
    if any(i['severity']=='P0' and i['status']!='rechecked' for candidate in store.all('candidate') for i in candidate['issues']):
        errors.append('发现未修复P0，当前环境暂停推荐与导出')
    return {'eligible':not errors,'state':'approved' if not errors else 'needs_recheck' if review else 'evidence_pending','errors':errors,'input_hash':hash_value,'review':review,'candidate_version':c['candidate_version']}
