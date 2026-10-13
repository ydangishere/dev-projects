"""Persistent human-governed workflow. SQLite is authoritative in local mode."""
import os, sqlite3, json
from pathlib import Path
from datetime import datetime, timezone, date as Date
from contextlib import contextmanager

BASE=Path(__file__).resolve().parent
STATES=['Draft Requirement','Ready for Design','Wireframe Review','Changes Requested','Ready for Dev','Blocked - Technical','In Development','Done']
DB=Path(os.getenv('DATABASE_PATH',str(BASE/'workspace'/'workflow.sqlite3')))
if not DB.is_absolute(): DB=BASE/DB
REQUIRED=['business_goal','user_flow','business_logic','edge_cases','acceptance_criteria']

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
@contextmanager
def db():
 DB.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 try:
  yield c;c.commit()
 except:
  c.rollback();raise
 finally:c.close()

def init():
 with db() as c:c.executescript('''
 CREATE TABLE IF NOT EXISTS modules(id INTEGER PRIMARY KEY,project TEXT NOT NULL,module TEXT NOT NULL,owner TEXT NOT NULL,owner_email TEXT NOT NULL,designer_email TEXT DEFAULT '',dev_email TEXT DEFAULT '',priority TEXT NOT NULL,deadline TEXT NOT NULL,requirements_url TEXT NOT NULL,figma_url TEXT DEFAULT '',github_url TEXT DEFAULT '',handoff_url TEXT DEFAULT '',deployment_url TEXT DEFAULT '',status TEXT NOT NULL DEFAULT 'Draft Requirement',business_goal TEXT DEFAULT '',user_flow TEXT DEFAULT '',business_logic TEXT DEFAULT '',edge_cases TEXT DEFAULT '',acceptance_criteria TEXT DEFAULT '',approved_by TEXT DEFAULT '',version INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS changes(id INTEGER PRIMARY KEY,module_id INTEGER NOT NULL,author TEXT NOT NULL,summary TEXT NOT NULL,reason TEXT NOT NULL,impact_design TEXT NOT NULL,impact_dev TEXT NOT NULL,confirmed_by TEXT DEFAULT '',created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,module_id INTEGER NOT NULL,actor TEXT NOT NULL,event TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,module_id INTEGER NOT NULL,recipient TEXT NOT NULL,channel TEXT NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT DEFAULT '',created_at TEXT NOT NULL,sent_at TEXT);
 CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY,module_id INTEGER NOT NULL,recipient TEXT NOT NULL,stage TEXT NOT NULL,ordinal INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(module_id,recipient,stage,ordinal));
 CREATE TABLE IF NOT EXISTS checks(id INTEGER PRIMARY KEY,module_id INTEGER NOT NULL,specialist TEXT NOT NULL,model TEXT NOT NULL,report TEXT NOT NULL,created_at TEXT NOT NULL);
 ''')

def _row(c,id):
 x=c.execute('SELECT * FROM modules WHERE id=?',(id,)).fetchone()
 if not x:raise ValueError('Module not found')
 return x

def record(c,id,actor,event,detail):c.execute('INSERT INTO events(module_id,actor,event,detail,created_at) VALUES(?,?,?,?,?)',(id,actor,event,detail,now()))

def notify(c,id,recipient,msg):
 if recipient:
  c.execute('INSERT INTO outbox(module_id,recipient,channel,message,created_at) VALUES(?,?,?,?,?)',(id,recipient,'email',msg,now()))
 if os.getenv('GOOGLE_CHAT_WEBHOOK'):
  if not c.execute("SELECT 1 FROM outbox WHERE module_id=? AND channel='chat' AND message=? AND status='pending'",(id,msg)).fetchone():
   c.execute('INSERT INTO outbox(module_id,recipient,channel,message,created_at) VALUES(?,?,?,?,?)',(id,'workspace','chat',msg,now()))

def create(project,module,owner,owner_email,designer_email,dev_email,priority,deadline,requirements_url):
 if not all([project.strip(),module.strip(),owner.strip(),owner_email.strip(),priority.strip(),deadline.strip(),requirements_url.strip()]):raise ValueError('Project/module/owner/email/priority/deadline/requirements link required')
 with db() as c:
  cur=c.execute('INSERT INTO modules(project,module,owner,owner_email,designer_email,dev_email,priority,deadline,requirements_url,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(project,module,owner,owner_email,designer_email,dev_email,priority,deadline,requirements_url,now()))
  id=cur.lastrowid;record(c,id,owner,'created','Draft Requirement');notify(c,id,owner_email,f'{project}/{module}: module registered. Complete Definition of Ready. {requirements_url}');return id

def _transition(c,id,expected,next_state,actor,detail):
 m=_row(c,id)
 if m['status'] not in expected:raise ValueError('Cannot transition from '+m['status']+' to '+next_state)
 c.execute('UPDATE modules SET status=?,updated_at=?,version=version+1 WHERE id=?',(next_state,now(),id))
 record(c,id,actor,'status',m['status']+' → '+next_state+'. '+detail)
 return m

def definition_ready(id,actor,fields):
 if not actor.strip():raise ValueError('Confirmation owner required')
 for f in REQUIRED:
  if not (fields.get(f) or '').strip():raise ValueError('Definition of Ready missing: '+f)
 with db() as c:
  m=_row(c,id)
  if m['status'] not in ('Draft Requirement','Changes Requested'):raise ValueError('Definition of Ready only in draft or after changes')
  c.execute('UPDATE modules SET '+','.join(f+'=?' for f in REQUIRED)+' WHERE id=?',tuple(fields[f].strip() for f in REQUIRED)+(id,))
  _transition(c,id,('Draft Requirement','Changes Requested'),'Ready for Design',actor,'DoR complete and owner confirmed')
  notify(c,id,m['designer_email'],f'{m["project"]}/{m["module"]}: Ready for Design. Requirements: {m["requirements_url"]}')

def submit_wireframe(id,actor,figma_url):
 if not figma_url.startswith('https://www.figma.com/'):raise ValueError('Valid Figma URL required')
 with db() as c:
  m=_transition(c,id,('Ready for Design',),'Wireframe Review',actor,'Wireframe submitted')
  c.execute('UPDATE modules SET figma_url=? WHERE id=?',(figma_url,id))
  notify(c,id,m['owner_email'],f'{m["project"]}/{m["module"]}: Wireframe ready for review. {figma_url}')

def change_request(id,actor,summary,reason,impact_design,impact_dev,confirmed_by=''):
 if not all(x.strip() for x in [actor,summary,reason,impact_design,impact_dev]):raise ValueError('Change summary, reason and impacts required')
 with db() as c:
  m=_row(c,id)
  if m['status']=='Done':raise ValueError('Cannot amend done module; create a new change request/module')
  c.execute('INSERT INTO changes(module_id,author,summary,reason,impact_design,impact_dev,confirmed_by,created_at) VALUES(?,?,?,?,?,?,?,?)',(id,actor,summary,reason,impact_design,impact_dev,confirmed_by,now()))
  if m['status']!='Changes Requested':_transition(c,id,(m['status'],),'Changes Requested',actor,'Change Log recorded; rework required')
  record(c,id,actor,'change',summary)
  recipients={m['owner_email'],m['designer_email'],m['dev_email']}
  for address in recipients:notify(c,id,address,f'{m["project"]}/{m["module"]}: requirement change: {summary}. Design impact: {impact_design}. Dev impact: {impact_dev}. Review latest Docs and Change Log.')

def approve_handoff(id,actor,handoff_url):
 if not actor.strip() or not handoff_url.startswith('https://www.figma.com/'):raise ValueError('Named approver and valid Figma handoff required')
 with db() as c:
  m=_transition(c,id,('Wireframe Review',),'Ready for Dev',actor,'Design handoff approved')
  c.execute('UPDATE modules SET handoff_url=?,approved_by=? WHERE id=?',(handoff_url,actor,id))
  notify(c,id,m['dev_email'],f'{m["project"]}/{m["module"]}: Ready for Dev. Requirements {m["requirements_url"]}; Handoff {handoff_url}; check technical constraints.')

def technical_review(id,actor,blocked,notes,issue_url=''):
 if not actor.strip() or not notes.strip():raise ValueError('Reviewer and technical review note required')
 with db() as c:
  m=_row(c,id)
  nxt='Blocked - Technical' if blocked else 'In Development'
  _transition(c,id,('Ready for Dev','Blocked - Technical'),nxt,actor,notes)
  if issue_url:c.execute('UPDATE modules SET github_url=? WHERE id=?',(issue_url,id))
  for email in {m['owner_email'],m['designer_email']}:
   notify(c,id,email,f'{m["project"]}/{m["module"]}: technical review {nxt}. {notes} {issue_url}')

def complete(id,actor,deployment_url):
 if not actor.strip() or not deployment_url.startswith('https://'):raise ValueError('Dev name and deployed URL required')
 with db() as c:
  m=_transition(c,id,('In Development',),'Done',actor,'Implementation completed')
  c.execute('UPDATE modules SET deployment_url=? WHERE id=?',(deployment_url,id))
  notify(c,id,m['owner_email'],f'{m["project"]}/{m["module"]}: complete. Verify deployment {deployment_url}')

def schedule_reminders(today=None):
 """Idempotent queued reminders, maximum 3 per recipient per stage; call daily from OS scheduler."""
 today=today or now()[:10];made=0
 with db() as c:
  rows=c.execute("SELECT * FROM modules WHERE deadline<? AND status NOT IN ('Done')",(today,)).fetchall()
  for m in rows:
   responsible=m['designer_email'] if m['status'] in ('Ready for Design','Changes Requested') else m['dev_email'] if m['status'] in ('Ready for Dev','Blocked - Technical','In Development') else m['owner_email']
   if not responsible:continue
   count=c.execute('SELECT COUNT(*) FROM reminders WHERE module_id=? AND recipient=? AND stage=?',(m['id'],responsible,m['status'])).fetchone()[0]
   if count>=3:continue
   last=c.execute('SELECT created_at FROM reminders WHERE module_id=? AND recipient=? AND stage=? ORDER BY id DESC LIMIT 1',(m['id'],responsible,m['status'])).fetchone()
   interval=max(1,int(os.getenv('REMINDER_INTERVAL_DAYS','1')))
   if last and (Date.fromisoformat(today)-Date.fromisoformat(last['created_at'][:10])).days<interval:continue
   try:
    c.execute('INSERT INTO reminders(module_id,recipient,stage,ordinal,created_at) VALUES(?,?,?,?,?)',(m['id'],responsible,m['status'],count+1,today+'T00:00:00+00:00'))
    notify(c,m['id'],responsible,f'Reminder {count+1}/3: {m["project"]}/{m["module"]} is overdue since {m["deadline"]}; current status {m["status"]}. Update tracker or ask PM to reschedule.')
    record(c,m['id'],'scheduler','reminder',f'{responsible} #{count+1}/3');made+=1
   except sqlite3.IntegrityError:pass
 return made

def snapshot():
 with db() as c:
  modules=[dict(x) for x in c.execute('SELECT * FROM modules ORDER BY updated_at DESC,id DESC')]
  for m in modules:
   for key,table in [('changes','changes'),('events','events'),('outbox','outbox'),('checks','checks')]:
    m[key]=[dict(x) for x in c.execute(f'SELECT * FROM {table} WHERE module_id=? ORDER BY id DESC LIMIT 30',(m['id'],))]
  return modules
