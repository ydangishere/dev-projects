import os, json, html
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent/'.env')
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import engine as e
from services import generate_concept, send_email, send_chat

app=FastAPI(title='Website Builder Agent — local MVP',docs_url='/api')
app.mount('/static',StaticFiles(directory=Path(__file__).parent/'static'),name='static')
templates=Jinja2Templates(directory=Path(__file__).parent/'templates')

@app.on_event('startup')
def startup():e.init_db()

def redirect(msg=''):return RedirectResponse('/?message='+msg,status_code=303)
def problem(ex):return redirect('Error: '+str(ex))

@app.get('/',response_class=HTMLResponse)
def home(request:Request,message:str=''):
 with e.connection() as c:
  p=dict(e.project(c));members=[dict(x) for x in c.execute('SELECT * FROM members WHERE active=1 ORDER BY name')]
  rounds=[dict(x) for x in c.execute('SELECT * FROM rounds ORDER BY id DESC')]
  artifacts=[dict(x) for x in c.execute('SELECT * FROM artifacts ORDER BY id DESC LIMIT 70')]
  events=[dict(x) for x in c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 25')]
  for r in rounds:r['stats']=e.review_status(c,r)
  current=e.review(c,p['step']);current=next((r for r in rounds if current and r['id']==current['id']),None)
  return templates.TemplateResponse(request,'index.html',{'project':p,'members':members,'rounds':rounds,'current':current,'artifacts':artifacts,'events':events,'steps':e.STEPS,'message':message,'figma':os.getenv('FIGMA_URL',''),'docs':os.getenv('REQUIREMENTS_URL','')})

@app.post('/members')
def members(name:str=Form(...),email:str=Form(...),chat_target:str=Form('')):
 try:e.add_member(name.strip(),email.strip(),chat_target.strip());return redirect('Member added')
 except Exception as x:return problem(x)

@app.post('/artifacts')
def artifacts(step:int=Form(...),kind:str=Form(...),content:str=Form(''),url:str=Form('')):
 try:
  if step<1 or step>9 or (not content.strip() and not url.strip()):raise ValueError('Add content or URL')
  e.add_artifact(step,kind,content,url);return redirect('Artifact saved')
 except Exception as x:return problem(x)

@app.post('/rounds')
def rounds(step:int=Form(...),url:str=Form(...),due_at:str=Form('')):
 try:e.create_round(step,url,due_at or None);return redirect('Review started')
 except Exception as x:return problem(x)

@app.post('/responses')
def responses(round_id:int=Form(...),member_id:int=Form(...),decision:str=Form(...),comment:str=Form('')):
 try:e.respond(round_id,member_id,decision,comment);return redirect('Response saved')
 except Exception as x:return problem(x)

@app.post('/advance')
def advance(next_step:int=Form(...)):
 try:e.set_step(next_step);return redirect('Step advanced')
 except Exception as x:return problem(x)

@app.post('/remind')
async def remind(round_id:int=Form(...),member_id:int=Form(...),channel:str=Form(...)):
 try:
  with e.connection() as c:
   r,candidates=e.reminder_candidates(c,round_id)
   item=next((x for x in candidates if x['member']['id']==member_id),None)
   if not item:raise ValueError('Reviewer already replied or maximum 3 reminders reached')
   member=item['member'];n=item['next_number']
  msg=f'VietPay Website — reminder {n}/3. Please review and explicitly respond (Approved / No Objection / Changes Requested): {r["artifact_url"]}'
  if channel=='email':send_email(member['email'],f'[VietPay] Review reminder {n}/3',msg)
  elif channel=='chat':await send_chat(f'@{member["name"]} — {msg}')
  else:raise ValueError('Unsupported channel')
  e.record_reminder(round_id,member_id,channel)
  return redirect(f'Reminder {n}/3 sent')
 except Exception as x:return problem(x)

@app.post('/invite')
async def invite(round_id:int=Form(...),channel:str=Form(...)):
 """Explicit user-triggered initial announcement; reminders remain individually capped."""
 try:
  with e.connection() as c:
   r=c.execute('SELECT * FROM rounds WHERE id=? AND state="open"',(round_id,)).fetchone()
   if not r:raise ValueError('No open review')
   ms=[dict(x) for x in c.execute('SELECT * FROM members WHERE active=1')]
  msg=f'VietPay Website Step {r["step"]}: please review and provide an explicit decision/comment at: {r["artifact_url"]}'
  if channel=='email':
   for m in ms:send_email(m['email'],'[VietPay] Review requested',msg)
  elif channel=='chat':await send_chat(msg)
  else:raise ValueError('Unsupported channel')
  with e.connection() as c:e.log(c,'review_invitation',f'{channel} round {round_id}')
  return redirect('Invitations sent')
 except Exception as x:return problem(x)

@app.post('/generate')
async def generate(provider:str=Form(...),brief:str=Form(...)):
 try:
  with e.connection() as c:
   if e.project(c)['step']!=3:raise ValueError('Concept generation only at Step 3')
  output=await generate_concept(provider,brief)
  e.add_artifact(3,'concept_'+provider,output)
  return redirect(provider+' concept generated')
 except Exception as x:return problem(x)

@app.post('/codex')
def codex(step:int=Form(...),task:str=Form(...)):
 try:
  with e.connection() as c:
   if e.project(c)['step']!=step:raise ValueError('Cannot run Codex for inactive step')
  if step not in (4,6,7,8,9):raise ValueError('Codex tasks only for build/QA/demo steps')
  root=Path(__file__).parent/'workspace'/'site'
  result=e.run_codex(task,root)
  e.add_artifact(step,'codex_run',json.dumps(result,ensure_ascii=False,indent=2))
  return redirect('Codex finished: '+('OK' if result['ok'] else 'Error — inspect run log'))
 except Exception as x:return problem(x)

@app.get('/export',response_class=PlainTextResponse)
def export():
 with e.connection() as c:
  result={table:[dict(x) for x in c.execute(f'SELECT * FROM {table}')] for table in ('projects','members','rounds','responses','reminders','artifacts','events')}
 return PlainTextResponse(json.dumps(result,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':'attachment; filename="vietpay-agent-state.json"'})
