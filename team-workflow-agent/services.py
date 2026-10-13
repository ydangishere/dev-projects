"""Optional connectors; missing configuration must never pretend success."""
import os,json,re,smtplib,ssl
from email.message import EmailMessage
from urllib.request import Request,urlopen
from urllib.parse import quote


def http_json(url,method='GET',payload=None,headers=None):
 data=json.dumps(payload).encode() if payload is not None else None
 req=Request(url,data=data,headers={'User-Agent':'WorkflowAgent/1','Content-Type':'application/json',**(headers or {})},method=method)
 with urlopen(req,timeout=35) as res:return json.load(res)

def send_message(item):
 if item['channel']=='email':
  keys=['SMTP_HOST','SMTP_USER','SMTP_PASSWORD','SMTP_FROM']
  if not all(os.getenv(x) for x in keys):raise RuntimeError('SMTP is not configured')
  msg=EmailMessage();msg['From']=os.environ['SMTP_FROM'];msg['To']=item['recipient'];msg['Subject']='[Workflow] Action required';msg.set_content(item['message'])
  with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=20) as c:
   c.starttls(context=ssl.create_default_context());c.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);c.send_message(msg)
 elif item['channel']=='chat':
  url=os.getenv('GOOGLE_CHAT_WEBHOOK')
  if not url:raise RuntimeError('Google Chat webhook is missing')
  http_json(url,'POST',{'text':item['message']})
 else:raise ValueError('Unknown channel')

def send_outbox(db,max_items=25):
 sent=failed=0
 with db() as c:
  entries=[dict(r) for r in c.execute("SELECT * FROM outbox WHERE status IN ('pending','error') AND attempts<3 ORDER BY id LIMIT ?",(max_items,))]
 for m in entries:
  try:
   send_message(m)
   with db() as c:c.execute("UPDATE outbox SET status='sent',attempts=attempts+1,last_error='',sent_at=datetime('now') WHERE id=?",(m['id'],))
   sent+=1
  except Exception as ex:
   with db() as c:c.execute("UPDATE outbox SET status='error',attempts=attempts+1,last_error=? WHERE id=?",(str(ex)[:400],m['id']))
   failed+=1
 return {'sent':sent,'failed':failed}

def make_issue(title,body):
 repo=os.getenv('GITHUB_REPOSITORY');token=os.getenv('GITHUB_TOKEN')
 if not (repo and token and re.fullmatch(r'[\w.-]+/[\w.-]+',repo)):
  raise RuntimeError('GITHUB_REPOSITORY/GITHUB_TOKEN not configured; record a manual issue URL')
 r=http_json('https://api.github.com/repos/'+repo+'/issues','POST',{'title':title,'body':body,'labels':['technical-constraint']},{'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
 return r['html_url']

def figma_text(url):
 from urllib.parse import urlparse,parse_qs
 token=os.getenv('FIGMA_TOKEN')
 if not token:raise RuntimeError('FIGMA_TOKEN not configured')
 m=re.search(r'/design/([A-Za-z0-9]+)',url)
 if not m:raise ValueError('Not a Figma Design URL')
 node=parse_qs(urlparse(url).query).get('node-id',[None])[0]
 if not node:raise ValueError('Figma URL requires node-id')
 node=node.replace('-',':')
 data=http_json(f'https://api.figma.com/v1/files/{m.group(1)}/nodes?ids={quote(node)}',headers={'X-Figma-Token':token})
 root=data.get('nodes',{}).get(node,{}).get('document',{})
 collected=[]
 def walk(obj):
  if len(collected)>=100: return
  if obj.get('type')=='TEXT' and obj.get('characters'):collected.append(obj['characters'][:1000])
  for child in obj.get('children',[]):walk(child)
 walk(root)
 return '\n'.join(collected)[:12000]

PROMPTS={
 'requirements':'You are a Business Requirements QA agent. Check DoR for ambiguity, missing edge cases, inconsistent business logic and untestable acceptance criteria. Return risks, targeted questions, recommended acceptance criteria. Never approve automatically.',
 'design':'You are a UX Design Review agent. Compare linked Figma text/design notes with business goals, DoR and acceptance criteria. Identify missing states, navigation and usability gaps; clearly state visual layout cannot be verified from text. Never approve automatically.',
 'technical':'You are a Technical Feasibility agent. Identify integration dependencies, backend/API assumptions, edge cases, security and deployment risks. Propose GitHub Issue drafts, not automatic approvals.'}

def ai_check(specialist,context):
 if specialist not in PROMPTS:raise ValueError('Unknown specialist')
 key=os.getenv('OPENAI_API_KEY');model=os.getenv('OPENAI_MODEL','gpt-4.1-mini')
 if not key:raise RuntimeError('OPENAI_API_KEY not configured')
 res=http_json('https://api.openai.com/v1/chat/completions','POST',{'model':model,'messages':[{'role':'system','content':PROMPTS[specialist]},{'role':'user','content':context[:24000]}],'temperature':0.2},{'Authorization':'Bearer '+key})
 return model,res['choices'][0]['message']['content']

def mirror_to_sheets(modules):
 """One-way tracker mirror. SQLite remains authoritative; no unapproved external edits imported."""
 path=os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON');sid=os.getenv('GOOGLE_SHEET_ID');tab=os.getenv('GOOGLE_SHEET_TAB','Modules')
 if not (path and sid):raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON and GOOGLE_SHEET_ID required')
 from google.oauth2 import service_account
 from google.auth.transport.requests import Request as GoogleRequest
 creds=service_account.Credentials.from_service_account_file(path,scopes=['https://www.googleapis.com/auth/spreadsheets'])
 creds.refresh(GoogleRequest())
 headers={'Authorization':'Bearer '+creds.token}
 cols=['id','project','module','owner','owner_email','designer_email','dev_email','priority','deadline','status','version','requirements_url','figma_url','handoff_url','github_url','deployment_url','approved_by','updated_at']
 vals=[cols]+[[str(m.get(col,'') or '') for col in cols] for m in modules]
 range_name=quote("'"+tab.replace("'","''")+"'!A1:R",safe='!')
 url=f'https://sheets.googleapis.com/v4/spreadsheets/{quote(sid)}/values/{range_name}?valueInputOption=RAW'
 return http_json(url,'PUT',{'range':f"'{tab}'!A1:R",'majorDimension':'ROWS','values':vals},headers)
