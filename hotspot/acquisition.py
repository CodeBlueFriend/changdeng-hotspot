"""Deterministic manual JSON adapter. Never infers platform facts from titles."""
import copy
import re
import time
from datetime import datetime
from decimal import Decimal
from .common import now, digest, read, require, validate, redact, safe_url, GateError
from .store import uid

PARSER = 'manual-json/1.0.0'
TAGS = {'地名文旅':['古城','旅游','景区','地名'], '文物考古':['考古','文物','遗址'], '影视游戏':['电影','电视剧','游戏'], '美食民俗':['美食','民俗','节气'], '科技工程':['科技','大桥','工程'], '节庆纪念':['纪念','节日']}

def classify(title):
    return {'rule_tags':[k for k,terms in TAGS.items() if any(t in title for t in terms)] or ['其他'], 'ai_tags':[], 'version':'keywords/1.0.0', 'basis':'标题关键词，仅检索归档，不判断实体或历史真实性'}

def heat(value, unit=None):
    require(value is None or (isinstance(value,(str,int,float)) and not isinstance(value,bool)), '热度类型无效')
    raw = None if value is None else str(value)
    result={'raw_value':raw, 'normalized_decimal':None, 'metric_name':None, 'unit':unit, 'approximate':False}
    if raw is not None:
        # Conversion allowed only with explicitly supplied metric units; never means views.
        result['approximate'] = bool(re.search('[万亿]',raw))
        if unit == '热度指数' and re.fullmatch(r'\d+(?:\.\d+)?[万亿]?',raw):
            factor=Decimal('10000') if raw.endswith('万') else Decimal('100000000') if raw.endswith('亿') else Decimal(1)
            result['normalized_decimal']=format(Decimal(raw.rstrip('万亿'))*factor,'f')
            result['metric_name']='heat_index'
    return result

def normalize(payload, snapshot_id):
    require(isinstance(payload,dict), '手工输入必须为JSON对象')
    items=payload.get('items', [payload] if 'title' in payload else None)
    require(isinstance(items,list), '缺少items数组或title字段')
    require(items or payload.get('allow_empty') is True, '未声明正常空结果，进入隔离')
    require(len(items)<=1000, '单次最多1000条')
    records=[]; seen=set(); duplicates=0
    for index,item in enumerate(items):
        require(isinstance(item,dict), '条目必须为对象')
        title=item.get('title'); require(isinstance(title,str) and bool(title.strip()), '标题为空或字段漂移')
        sid=item.get('id')
        require(sid is None or isinstance(sid,(str,int)) and not isinstance(sid,bool), 'ID必须是字符串或整数，不能是浮点')
        sid=None if sid is None else str(sid)
        key=('id',sid) if sid is not None else ('title',title)
        if key in seen:
            duplicates+=1; continue
        seen.add(key)
        rank=item.get('rank'); require(rank is None or type(rank) is int and rank>0, '排名必须是正整数或空')
        pointer=f'/items/{index}' if 'items' in payload else ''
        url=safe_url(item.get('url'))
        record={'record_id':'HOT-'+digest([snapshot_id,index,sid,title])[:20], 'source_item_id':sid, 'title_raw':title,
            'title_normalized':' '.join(title.split()), 'url':url,
            'rank':{'value':rank,'basis':'provided' if rank else 'none','raw':str(rank) if rank else None},
            'heat':heat(item.get('heat'), item.get('unit')), 'category_raw':item.get('category'),
            'event_time_raw':str(item['event_time']) if item.get('event_time') is not None else None,
            'event_time_semantics':'unknown' if item.get('event_time') is not None else 'not_provided',
            'field_mappings':[{'field':field,'locator_kind':'json_pointer','locator':pointer+'/'+source} for field,source in [('title_raw','title'),('source_item_id','id'),('url','url'),('rank.raw','rank'),('heat.raw_value','heat'),('heat.unit','unit'),('category_raw','category'),('event_time_raw','event_time')] if source in item], 'cluster_id':None}
        records.append(record)
    return records, duplicates, len(items)

def import_manual(store, payload, parser_version=PARSER, replay_of=None):
    fixture=bool(payload.get('is_fixture',False)) if isinstance(payload,dict) else False
    require(not fixture or store.environment=='test','构造样例不能进入生产')
    run=uid('RUN'); sid=uid('SNAP')
    store.event('run_started',{'run_id':run,'source':'manual_import','capture_kind':'replay' if replay_of else 'manual'})
    cleaned=redact(payload)
    raw=store.archive(cleaned)
    snapshot={'schema_version':'1.0.0','snapshot_id':sid,'run_id':run,'source_id':'manual_import','upstream_family_id':'manual_unverified',
        'board_type':'manual','capture_kind':'replay' if replay_of else 'manual','environment':store.environment,'is_fixture':fixture,
        'fetched_at':now(),'source_updated_at':None,'provider_fetched_at':None,'window_start':None,'window_end':None,
        'cache_status':'unknown','source_freshness':'unknown','status':'valid','quality_gate':'needs_review','business_error_code':None,
        'parser_version':parser_version,'raw':raw,'raw_absence_reason':None,
        'coverage':{'returned_count':0,'source_total':None,'truncated':None,'scope':'用户手工提交，未验证任何平台榜单覆盖','pagination_complete':None},
        'records':[],'warnings':['手工线索；来源时间未知；不证明上榜、现代事件或历史关系。']}
    try:
        records,duplicates,count=normalize(cleaned,sid)
        snapshot['records']=records
        snapshot['coverage']['returned_count']=count
        if duplicates:
            snapshot['warnings'].append(f'同次输入重复条目{duplicates}条已去重，不累加热度。')
        snapshot['status']='valid' if records else 'empty_valid'
        if isinstance(cleaned,dict) and cleaned.get('truncated') is True:
            snapshot['status']='partial'; snapshot['coverage']['truncated']=True
            snapshot['coverage']['scope']=f'用户提交的截断片段，共{count}行；非完整榜单'
        validate('snapshot',snapshot)
    except GateError as exc:
        snapshot['records']=[]; snapshot['status']='schema_changed'; snapshot['quality_gate']='quarantined'; snapshot['warnings'].append(str(exc))
    validate('snapshot',snapshot)
    store.put('snapshot',sid,snapshot)
    for record in snapshot['records']:
        store.put('classification',record['record_id'],{'record_id':record['record_id'],'platform_tags':record['category_raw'],**classify(record['title_raw'])})
    store.event('run_finished',{'run_id':run,'snapshot_id':sid,'status':snapshot['status'],'replay_of':replay_of})
    return snapshot

def replay(store, snapshot_id):
    original=store.get('snapshot',snapshot_id)
    path=store.verify_file(original['raw'])
    result=import_manual(store,read(path),replay_of=snapshot_id)
    def comparable(s):
        return [{k:v for k,v in r.items() if k!='record_id'} for r in s['records']]
    return {'original':snapshot_id,'snapshot':result,'changed':comparable(original)!=comparable(result), 'original_parser':original['parser_version'],'new_parser':PARSER}

def collect(store):
    # No network call is made until a source's permission and exact fields are verified.
    run={'run_id':uid('RUN'),'source_id':'douyin_official_hot_words','status':'NOT_CONFIGURED','requested':False,'at':now(), 'reason':'尚无已核验的来源能力与凭据引用；未发送请求，无快照。'}
    store.event('collection_not_configured',run)
    return run

def freshness(snapshot, at=None, budget=10800):
    source=snapshot.get('source_updated_at')
    if not source:return 'unknown'
    age=((at or datetime.fromisoformat(now()))-datetime.fromisoformat(source)).total_seconds()
    return 'clock_anomaly' if age<0 else 'stale' if age>budget else 'within_budget'

def trend(snapshots, source_item_id):
    points=[]; seen=set()
    for s in snapshots:
        if s['status'] not in ('valid','partial','empty_valid') or s['quality_gate']!='usable' or not s['source_updated_at'] or s['capture_kind']=='replay':continue
        for r in s['records']:
            if r['source_item_id'] != source_item_id or not r['heat']['normalized_decimal']:continue
            key=(s['source_id'],s['board_type'],r['heat']['metric_name'],r['heat']['unit'])
            observation=(key,s['source_updated_at'])
            if observation not in seen:
                points.append((key,s['source_updated_at'],r['heat']['normalized_decimal']));seen.add(observation)
    if len(points)<2 or len({p[0] for p in points})!=1:return {'status':'unknown','reason':'不足两个同来源同榜单同口径、不同源版本的有效观测'}
    points.sort(key=lambda x:x[1])
    return {'status':'preliminary' if len(points)>=3 else 'two_points','points':points,'delta':str(Decimal(points[-1][2])-Decimal(points[0][2])),'prediction':None}
