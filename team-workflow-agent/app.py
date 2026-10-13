"""BA/PM/Designer/Dev collaboration dashboard — loopback-only MVP."""
import os, json, sys
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent/'.env')
import engine as e
import services as s
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

BASE=Path(__file__).resolve().parent
app=FastAPI(title='Team Workflow Automation & AI Review',docs_url='/api')
templates=Jinja2Templates(directory=str(BASE/'templates'))
app.mount('/static',StaticFiles(directory=str(BASE/'static')),name='static')
@app.on_event('startup')
def start():e.init()
def jump(msg):
 from urllib.parse import urlencode
 return RedirectResponse('/?'+urlencode({'message':msg}),status_code=303)
def wrap(action):
 try:return jump(action() or 'Saved')
 except Exception as ex:return jump('ERROR: '+str(ex))

@app.get('/')
def home(request:Request,message:str=''):
 mods=e.snapshot()
 with e.db() as c:
  pending=c.execute("SELECT COUNT(*) FROM outbox WHERE status IN ('pending','error')").fetchone()[0]
 return templates.TemplateResponse(request,'index.html',{'modules':mods,'message':message,'today':date.today().isoformat(),'pending':pending,'states':e.STATES})

@app.post('/modules')
def create(project:str=Form(...),module:str=Form(...),owner:str=Form(...),owner_email:str=Form(...),designer_email:str=Form(''),dev_email:str=Form(''),priority:str=Form(...),deadline:str=Form(...),requirements_url:str=Form(...)):
 return wrap(lambda:'Module #'+str(e.create(project,module,owner,owner_email,designer_email,dev_email,priority,deadline,requirements_url))+' created')

@app.post('/ready/{id}')
def ready(id:int,actor:str=Form(...),business_goal:str=Form(...),user_flow:str=Form(...),business_logic:str=Form(...),edge_cases:str=Form(...),acceptance_criteria:str=Form(...)):
 return wrap(lambda:(e.definition_ready(id,actor,locals_for_dor(business_goal,user_flow,business_logic,edge_cases,acceptance_criteria)),'Definition of Ready confirmed')[1])
def locals_for_dor(business_goal,user_flow,business_logic,edge_cases,acceptance_criteria):
 return dict(business_goal=business_goal,user_flow=user_flow,business_logic=business_logic,edge_cases=edge_cases,acceptance_criteria=acceptance_criteria)

@app.post('/wireframe/{id}')
def wireframe(id:int,actor:str=Form(...),figma_url:str=Form(...)):
 return wrap(lambda:(e.submit_wireframe(id,actor,figma_url),'Wireframe review started')[1])

@app.post('/change/{id}')
def change(id:int,actor:str=Form(...),summary:str=Form(...),reason:str=Form(...),impact_design:str=Form(...),impact_dev:str=Form(...),confirmed_by:str=Form('')):
 return wrap(lambda:(e.change_request(id,actor,summary,reason,impact_design,impact_dev,confirmed_by),'Requirement change recorded; stage reopened')[1])

@app.post('/handoff/{id}')
def handoff(id:int,actor:str=Form(...),handoff_url:str=Form(...)):
 return wrap(lambda:(e.approve_handoff(id,actor,handoff_url),'Design handoff approved')[1])

@app.post('/technical/{id}')
def technical(id:int,actor:str=Form(...),blocked:bool=Form(False),notes:str=Form(...),create_issue:bool=Form(False),issue_url:str=Form('')):
 def execute():
  url=issue_url
  if blocked and create_issue:
   with e.db() as c:m=dict(e._row(c,id))
   url=s.make_issue(f'Technical constraint: {m["project"]} / {m["module"]}',f'{notes}\n\nRequirements: {m["requirements_url"]}\nFigma: {m["handoff_url"]}')
  e.technical_review(id,actor,blocked,notes,url)
  return ('Blocked: '+url) if blocked else 'Technical review passed; in development'
 return wrap(execute)

@app.post('/done/{id}')
def done(id:int,actor:str=Form(...),deployment_url:str=Form(...)):
 return wrap(lambda:(e.complete(id,actor,deployment_url),'Module done')[1])

@app.post('/agent/{id}')
def agent(id:int,role:str=Form(...),extra_context:str=Form(''),include_figma:bool=Form(False)):
 def execute():
  with e.db() as c:
   m=dict(e._row(c,id));ch=[dict(r) for r in c.execute('SELECT * FROM changes WHERE module_id=? ORDER BY id DESC LIMIT 12',(id,))]
  if include_figma and m['figma_url']:
   extra=extra_context+'\nFigma text:\n'+s.figma_text(m['figma_url'])
  else:extra=extra_context
  context=json.dumps({'module':m,'change_log':ch,'user_supplied_notes':extra},ensure_ascii=False)
  model,report=s.ai_check(role,context)
  with e.db() as c:
   c.execute('INSERT INTO checks(module_id,specialist,model,report,created_at) VALUES(?,?,?,?,?)',(id,role,model,report,e.now()))
   e.record(c,id,'AI '+role,'advisory','Report generated; human approval still required')
  return 'AI '+role+' report saved'
 return wrap(execute)

@app.post('/reminders')
def reminders():return wrap(lambda:str(e.schedule_reminders())+' overdue reminders queued')
@app.post('/dispatch')
def dispatch():return wrap(lambda:'Dispatch results: '+json.dumps(s.send_outbox(e.db)))
@app.post('/sheets')
def sheets():return wrap(lambda:'Google Sheets updated: '+str(s.mirror_to_sheets(e.snapshot()).get('updatedRows'))+' rows')

@app.get('/modules/{id}/handoff.json')
def handoff_export(id:int):
 with e.db() as c:
  m=dict(e._row(c,id))
  if m['status'] not in ('Ready for Dev','Blocked - Technical','In Development','Done'):
   return JSONResponse({'error':'Handoff is not approved yet'},status_code=409)
  changes=[dict(x) for x in c.execute('SELECT * FROM changes WHERE module_id=? ORDER BY id',(id,))]
  checks=[dict(x) for x in c.execute('SELECT * FROM checks WHERE module_id=? ORDER BY id',(id,))]
  return {'module':m,'change_log':changes,'ai_reviews':checks,'warning':'Informational handoff; check human approvals and sources before implementation'}

@app.get('/health')
def health():return {'status':'ok','service':'team-workflow-agent'}

if __name__=='__main__':
 e.init()
 if len(sys.argv)>1 and sys.argv[1]=='reminders':print('queued:',e.schedule_reminders());print('delivery:',s.send_outbox(e.db) if os.getenv('ENABLE_SCHEDULED_DELIVERY')=='1' else 'not enabled')
 elif len(sys.argv)>1 and sys.argv[1]=='dispatch':print(s.send_outbox(e.db))
 else:print('Use: uvicorn app:app --host 127.0.0.1 --port 8010')
