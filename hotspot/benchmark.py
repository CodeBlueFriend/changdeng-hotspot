"""Metrics consume human-labelled data; synthetic tests never count as gold."""
import math
from .common import require, digest, now

def ratio(n,d):
    if not d:return {'numerator':n,'denominator':d,'value':None,'wilson_95':None}
    p=n/d; z=1.959963984540054; center=(p+z*z/(2*d))/(1+z*z/d)
    margin=z*math.sqrt(p*(1-p)/d+z*z/(4*d*d))/(1+z*z/d)
    return {'numerator':n,'denominator':d,'value':p,'wilson_95':[center-margin,center+margin]}

def evaluate(gold,predictions):
    require(gold.get('human_finalized') is True and gold.get('locked') is True and gold.get('reviewers'), '金标准需人工定稿、锁定及复核记录')
    require(gold.get('contaminated') is False,'锁定集污染状态需明确为false')
    cases=gold['cases']; rows=predictions['predictions']
    require(not any(c.get('is_synthetic',True) for c in cases),'构造反例不能作为真实金标准')
    require(len({c['id'] for c in cases})==len(cases),'金标准ID重复')
    require(len({r['id'] for r in rows})==len(rows),'预测ID重复')
    by={r['id']:r for r in rows}
    require(set(by)=={c['id'] for c in cases},'必须覆盖完整锁定集；不能套用展示5条上限')
    require(all(r.get('decision') in ('recommend','hold','reject') for r in rows),'预测结论无效')
    require(all(c.get('label') in ('positive','negative','disputed') for c in cases),'金标标签无效')
    tp=fp=fn=direct=direct_hit=disputed=p0=critical=supported=negative=0;failures=[]
    for c in cases:
        r=by[c['id']];rec=r['decision']=='recommend'
        require(type(r.get('p0_count')) is int and r['p0_count']>=0,'须逐条提供P0人工核对数')
        require(type(c.get('critical_claims')) is int and c['critical_claims']>0,'金标须预先枚举关键主张数')
        require(type(r.get('supported_critical_claims')) is int and 0<=r['supported_critical_claims']<=c['critical_claims'],'支持覆盖数无效')
        if rec:
            p0+=r['p0_count'];critical+=c['critical_claims'];supported+=r['supported_critical_claims']
        if c['label']=='disputed':disputed+=1; continue
        pos=c['label']=='positive'; negative+=int(not pos)
        correct=pos and r['p0_count']==0 and r['supported_critical_claims']==c['critical_claims']
        tp+=int(rec and correct);fp+=int(rec and not correct);fn+=int(pos and not (rec and correct))
        direct+=int(pos and c.get('direct') is True);direct_hit+=int(rec and correct and c.get('direct') is True)
        if rec!=pos or rec and not correct:failures.append(c['id'])
    precision=ratio(tp,tp+fp); recall=ratio(tp,tp+fn);dr=ratio(direct_hit,direct);coverage=ratio(supported,critical)
    sufficient=len(cases)==60 and tp+fp>=20 and tp+fn>=30 and direct>=20 and negative>=20
    passed=sufficient and precision['value']>=.95 and recall['value']>=.8 and dr['value']>=.8 and coverage['value']==1 and p0==0
    return {'status':'PASS' if passed else 'FAIL' if sufficient else 'INSUFFICIENT_SAMPLE','at':now(),'input_hash':digest([gold,predictions]),'scope':'人工分层锁定集的具体关联命题；非线上总体准确率','TP':tp,'FP':fp,'FN':fn,'disputed':disputed,'recommended_total':sum(r['decision']=='recommend' for r in rows),'precision':precision,'recall':recall,'direct_recall':dr,'critical_coverage':coverage,'P0':p0,'failures':failures,'cases':len(cases)}

def evaluate_repeats(gold,runs):
    require(len(runs)==3,'须提供3次完整独立运行')
    require(len({r.get('run_id') for r in runs})==3 and all(r.get('run_id') for r in runs),'运行ID必须唯一且非空')
    reports=[evaluate(gold,r) for r in runs]
    return {'status':'PASS' if all(r['status']=='PASS' for r in reports) else 'NOT_PASSED','runs':reports}
