"""Persistent workflow rules for VietPay Website Agent.
Every external write requires explicit user action. No inferred approvals.
"""
import os, sqlite3, json, datetime as dt, subprocess, shutil
from pathlib import Path
from contextlib import contextmanager

STEPS = [
 "Design System input", "Additional Requirements review", "Claude & GPT concepts", 
 "Selected concept → scaffold", "Scaffold review", "Desktop build & approval",
 "Mobile build", "Responsive QA: desktop/tablet/mobile", "GitHub Pages demo → backend handoff",
]
ROOT = Path(__file__).resolve().parent
DB = Path(os.getenv('DATABASE_PATH','./workspace/agent.sqlite3'))
if not DB.is_absolute(): DB = ROOT / DB

@contextmanager
def connection():
 DB.parent.mkdir(parents=True,exist_ok=True)
 con=sqlite3.connect(DB)
 con.row_factory=sqlite3.Row
 try:
  yield con
  con.commit()
 finally: con.close()

def utc(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def init_db():
 with connection() as c:
  c.executescript('''
  CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, step INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'in_progress', created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS members(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, chat_target TEXT DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS rounds(id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, step INTEGER NOT NULL, artifact_url TEXT NOT NULL, due_at TEXT, state TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, UNIQUE(project_id,step,state));
  CREATE TABLE IF NOT EXISTS responses(id INTEGER PRIMARY KEY, round_id INTEGER NOT NULL, member_id INTEGER NOT NULL, decision TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL, UNIQUE(round_id,member_id));
  CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, round_id INTEGER NOT NULL, member_id INTEGER NOT NULL, ordinal INTEGER NOT NULL, sent_at TEXT NOT NULL, channel TEXT NOT NULL, UNIQUE(round_id,member_id,ordinal));
  CREATE TABLE IF NOT EXISTS artifacts(id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, step INTEGER NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
  ''')
  if not c.execute('SELECT 1 FROM projects').fetchone():
   c.execute('INSERT INTO projects(name,step,created_at) VALUES(?,?,?)',('VietPay Website',1,utc()))

def project(c): return c.execute('SELECT * FROM projects ORDER BY id LIMIT 1').fetchone()
def log(c, event, detail): c.execute('INSERT INTO events(project_id,event,detail,created_at) VALUES(?,?,?,?)',(project(c)['id'],event,detail,utc()))

def add_artifact(step,kind,content,url=''):
 with connection() as c:
  c.execute('INSERT INTO artifacts(project_id,step,kind,content,url,created_at) VALUES(?,?,?,?,?,?)',(project(c)['id'],step,kind,content,url,utc()))
  log(c,'artifact',f'Step {step}: {kind}')

def latest(c,step,kind=None):
 if kind: return c.execute('SELECT * FROM artifacts WHERE step=? AND kind=? ORDER BY id DESC LIMIT 1',(step,kind)).fetchone()
 return c.execute('SELECT * FROM artifacts WHERE step=? ORDER BY id DESC LIMIT 1',(step,)).fetchone()

def review(c,step): return c.execute('SELECT * FROM rounds WHERE step=? AND state="open" ORDER BY id DESC LIMIT 1',(step,)).fetchone()

def review_status(c,r):
 members=c.execute('SELECT * FROM members WHERE active=1 ORDER BY name').fetchall()
 responses={x['member_id']:dict(x) for x in c.execute('SELECT * FROM responses WHERE round_id=?',(r['id'],)).fetchall()}
 answered=sum(m['id'] in responses for m in members)
 blocked=any(x['decision']=='changes_requested' for x in responses.values())
 return {'total':len(members),'answered':answered,'blocked':blocked,'complete':bool(members) and answered==len(members) and not blocked,'missing':[dict(m) for m in members if m['id'] not in responses], 'responses':responses}

def set_step(next_step):
 with connection() as c:
  p=project(c); cur=p['step']
  if next_step!=cur+1 or next_step>9: raise ValueError('Only the next step is permitted')
  if cur in (2,3,5,6,8):
   r=review(c,cur)
   if not r: raise ValueError('This step requires an open review round')
   status=review_status(c,r)
   if not status['complete']: raise ValueError('All active members must respond; requested changes must be resolved')
   c.execute('UPDATE rounds SET state="closed" WHERE id=?',(r['id'],))
  required={1:'design_system',3:'selected_concept',4:'scaffold',6:'desktop',7:'mobile',8:'qa_report',9:'demo_url'}
  kind=required.get(cur)
  if kind and not latest(c,cur,kind): raise ValueError(f'Missing required artifact: {kind}')
  if cur==2 and not latest(c,2,'requirements'): raise ValueError('Requirements document not recorded')
  if cur==3 and (not latest(c,3,'concept_claude') or not latest(c,3,'concept_gpt')): raise ValueError('Both independent Claude and GPT concepts are required')
  c.execute('UPDATE projects SET step=? WHERE id=?',(next_step,p['id']))
  log(c,'advance',f'{cur} → {next_step}')

def add_member(name,email,chat_target=''):
 with connection() as c:
  c.execute('INSERT INTO members(name,email,chat_target) VALUES(?,?,?)',(name,email,chat_target))
  log(c,'member_added',email)

def create_round(step,url,due_at=None):
 if step not in (2,3,5,6,8): raise ValueError('Review not used on this step')
 with connection() as c:
  if step!=project(c)['step']: raise ValueError('Open a review only for the active step')
  if review(c,step): raise ValueError('An open round already exists')
  if not c.execute('SELECT 1 FROM members WHERE active=1').fetchone(): raise ValueError('Add reviewers first')
  c.execute('INSERT INTO rounds(project_id,step,artifact_url,due_at,created_at) VALUES(?,?,?,?,?)',(project(c)['id'],step,url,due_at,utc()))
  log(c,'review_opened',f'Step {step}: {url}')

def respond(round_id,member_id,decision,comment):
 if decision not in ('approved','no_objection','changes_requested'): raise ValueError('Unsupported decision')
 with connection() as c:
  m=c.execute('SELECT * FROM members WHERE id=? AND active=1',(member_id,)).fetchone()
  r=c.execute('SELECT * FROM rounds WHERE id=? AND state="open"',(round_id,)).fetchone()
  if not m or not r: raise ValueError('Invalid member or review')
  c.execute('INSERT INTO responses(round_id,member_id,decision,comment,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(round_id,member_id) DO UPDATE SET decision=excluded.decision,comment=excluded.comment,updated_at=excluded.updated_at',(round_id,member_id,decision,comment,utc()))
  log(c,'review_response',f'{m["name"]}: {decision} (round {round_id})')

def reminder_candidates(c,round_id):
 r=c.execute('SELECT * FROM rounds WHERE id=? AND state="open"',(round_id,)).fetchone()
 if not r: raise ValueError('Round not open')
 status=review_status(c,r)
 candidates=[]
 for m in status['missing']:
  sent=c.execute('SELECT COUNT(*) n FROM reminders WHERE round_id=? AND member_id=?',(round_id,m['id'])).fetchone()['n']
  if sent<3: candidates.append({'member':m,'next_number':sent+1})
 return r,candidates

def record_reminder(round_id,member_id,channel):
 with connection() as c:
  r,items=reminder_candidates(c,round_id)
  match=next((x for x in items if x['member']['id']==member_id),None)
  if not match: raise ValueError('No reminder available: already responded or limit reached')
  c.execute('INSERT INTO reminders(round_id,member_id,ordinal,sent_at,channel) VALUES(?,?,?,?,?)',(round_id,member_id,match['next_number'],utc(),channel))
  log(c,'reminder',f'Round {round_id}, member {member_id}, #{match["next_number"]}, {channel}')

def run_codex(task,project_root):
 """Explicitly initiated only; subprocess works in isolated project folder."""
 if not shutil.which('codex'): raise RuntimeError('Codex CLI not installed/on PATH')
 target=Path(project_root).resolve()
 target.mkdir(parents=True,exist_ok=True)
 if ROOT not in target.parents and target != ROOT / 'workspace' / 'site':
  raise ValueError('Project path must be within this application directory')
 command=['codex','exec','--full-auto',task]
 p=subprocess.run(command,cwd=target,capture_output=True,text=True,timeout=900)
 return {'ok':p.returncode==0,'returncode':p.returncode,'stdout':p.stdout[-18000:],'stderr':p.stderr[-4000:]}
