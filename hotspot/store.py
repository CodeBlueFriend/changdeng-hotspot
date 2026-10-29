import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from .common import canonical, digest, sha, now, write, read, require, contained

DIRS = ['00_原始快照', '01_规范化数据', '02_历史关联候选', '03_审核与推荐', '04_选题导出', '05_运行与质量']

class Store:
    def __init__(self, project, environment='production'):
        require(environment in ('production', 'test'), '环境无效')
        self.project = Path(project).expanduser().resolve()
        self.environment = environment
        self.root = self.project / '01_选题库/热点中心' / environment
        for name in DIRS:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / DIRS[1] / 'hotspots.sqlite'
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS documents(kind TEXT, id TEXT, version INTEGER, body TEXT, hash TEXT,
              PRIMARY KEY(kind,id,version));
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, at TEXT, kind TEXT, body TEXT);
            CREATE TABLE IF NOT EXISTS receipts(key TEXT PRIMARY KEY, body TEXT);
            CREATE TABLE IF NOT EXISTS invalidations(kind TEXT, id TEXT, reason TEXT, at TEXT, PRIMARY KEY(kind,id));
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, kind, identity, obj, version=1):
        body = canonical(obj).decode()
        with self.db() as db:
            old = db.execute('SELECT hash FROM documents WHERE kind=? AND id=? AND version=?', (kind,identity,version)).fetchone()
            if old:
                require(old['hash'] == digest(obj), '同一版本不可覆盖；请增加版本号')
                return obj
            db.execute('INSERT INTO documents VALUES(?,?,?,?,?)', (kind,identity,version,body,digest(obj)))
        return obj

    def get(self, kind, identity, version=None):
        with self.db() as db:
            row = db.execute('SELECT * FROM documents WHERE kind=? AND id=?' + (' AND version=?' if version else '') + ' ORDER BY version DESC LIMIT 1', (kind,identity,version) if version else (kind,identity)).fetchone()
        require(row is not None, f'引用不存在：{kind}/{identity}')
        obj = json.loads(row['body'])
        require(digest(obj) == row['hash'], '数据库内容哈希不匹配')
        return obj

    def all(self, kind):
        with self.db() as db:
            rows = db.execute('SELECT d.* FROM documents d JOIN (SELECT id,MAX(version) v FROM documents WHERE kind=? GROUP BY id) x ON d.id=x.id AND d.version=x.v WHERE d.kind=? ORDER BY d.rowid DESC', (kind,kind)).fetchall()
        out = []
        for r in rows:
            obj=json.loads(r['body']); require(digest(obj)==r['hash'], '数据库哈希不匹配'); out.append(obj)
        return out

    def event(self, kind, body):
        with self.db() as db:
            db.execute('INSERT INTO events(at,kind,body) VALUES(?,?,?)', (now(),kind,canonical(body).decode()))

    def events(self):
        with self.db() as db:
            return [dict(r) | {'body':json.loads(r['body'])} for r in db.execute('SELECT * FROM events ORDER BY seq DESC LIMIT 200')]

    def archive(self, data, folder=DIRS[0]):
        content = canonical(data)
        relative = str(Path(folder) / (sha(content) + '.json'))
        path = self.root / relative
        if path.exists():
            require(sha(path.read_bytes()) == sha(content), '已有归档被改动')
        else:
            write(path, data)
        return {'relative_path':relative, 'sha256':sha(content), 'secrets_removed':True, 'redaction_note':'递归删除认证字段与常见内嵌凭据；保留去敏后的JSON，不代表原文真实性。'}

    def verify_file(self, ref):
        path = contained(self.root, ref['relative_path'])
        require(path.is_file() and sha(path.read_bytes()) == ref['sha256'], '归档缺失或哈希不匹配：' + ref['relative_path'])
        return path

    def invalidate(self, kind, identity, reason):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO invalidations VALUES(?,?,?,?)', (kind,identity,reason,now()))
        self.event('needs_recheck', {'kind':kind,'id':identity,'reason':reason})

    def invalid(self, kind, identity):
        with self.db() as db:
            row=db.execute('SELECT * FROM invalidations WHERE kind=? AND id=?',(kind,identity)).fetchone()
            return dict(row) if row else None

    def backup(self, destination):
        import shutil
        dest = Path(destination).resolve()
        require(not dest.exists(), '备份目标必须是新目录')
        require(not dest.is_relative_to(self.root), '备份不能位于运行目录内部')
        # Copy archives first, database snapshot last, under caller's single-writer process.
        shutil.copytree(self.root, dest, ignore=shutil.ignore_patterns('*.sqlite*', '.pending-*'))
        with self.db() as db, sqlite3.connect(dest / DIRS[1] / 'hotspots.sqlite') as target:
            db.backup(target)
        manifest={str(p.relative_to(dest)):sha(p.read_bytes()) for p in dest.rglob('*') if p.is_file()}
        write(dest/'backup-manifest.json', manifest)
        return {'backup':str(dest),'files':len(manifest)}

    @staticmethod
    def restore(backup, destination):
        import shutil
        backup=Path(backup).resolve(); destination=Path(destination).resolve()
        require(not destination.exists(), '仅恢复到全新目录，避免覆盖运行数据')
        for path, expected in read(backup/'backup-manifest.json').items():
            p=contained(backup,path); require(p.is_file() and sha(p.read_bytes())==expected, '备份哈希不匹配')
        shutil.copytree(backup,destination)
        return {'restored':str(destination)}

def uid(prefix):
    return prefix + '-' + uuid.uuid4().hex[:16]
