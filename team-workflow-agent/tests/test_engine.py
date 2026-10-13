import os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ['DATABASE_PATH']=tempfile.mktemp(suffix='.sqlite3')
import engine as e

class TeamWorkflowTests(unittest.TestCase):
 def setUp(self):
  e.init()
  self.id=e.create('VietPay','Homepage','Victor','victor@example.com','design@example.com','dev@example.com','P1','2026-10-10','https://docs.google.com/document/d/example')
 def fields(self):return {k:'Evidence for '+k for k in e.REQUIRED}
 def test_dor_guard(self):
  with self.assertRaisesRegex(ValueError,'missing'):e.definition_ready(self.id,'Victor',{'business_goal':'Goals'})
  with e.db() as c:self.assertEqual(e._row(c,self.id)['status'],'Draft Requirement')
 def test_full_flow(self):
  e.definition_ready(self.id,'Victor',self.fields())
  e.submit_wireframe(self.id,'Designer','https://www.figma.com/design/abc/Temp?node-id=1-2')
  e.approve_handoff(self.id,'Senior','https://www.figma.com/design/abc/Temp?node-id=1-2')
  e.technical_review(self.id,'Dev',False,'No technical blockers')
  e.complete(self.id,'Dev','https://demo.example.com')
  with e.db() as c:self.assertEqual(e._row(c,self.id)['status'],'Done')
 def test_early_handoff_rejected(self):
  with self.assertRaisesRegex(ValueError,'Cannot transition'):e.approve_handoff(self.id,'Senior','https://www.figma.com/design/abc')
 def test_changes_reopen(self):
  e.definition_ready(self.id,'Victor',self.fields())
  e.submit_wireframe(self.id,'Designer','https://www.figma.com/design/abc/Temp')
  e.change_request(self.id,'PM','Update checkout','Legal change','Change CTA','Update API','PM')
  with e.db() as c:
   self.assertEqual(e._row(c,self.id)['status'],'Changes Requested')
   self.assertEqual(c.execute('SELECT COUNT(*) FROM changes WHERE module_id=?',(self.id,)).fetchone()[0],1)
  e.definition_ready(self.id,'PM',self.fields())
  with e.db() as c:self.assertEqual(e._row(c,self.id)['status'],'Ready for Design')
 def test_constraint_blocked(self):
  e.definition_ready(self.id,'Victor',self.fields())
  e.submit_wireframe(self.id,'Designer','https://www.figma.com/design/abc/Temp')
  e.approve_handoff(self.id,'Senior','https://www.figma.com/design/abc/Temp')
  e.technical_review(self.id,'Dev',True,'No API contract','https://github.com/ydangishere/dev-projects/issues/1')
  with self.assertRaisesRegex(ValueError,'Cannot transition'):e.complete(self.id,'Dev','https://demo.example.com')
  e.technical_review(self.id,'Dev',False,'Contract agreed')
  with e.db() as c:self.assertEqual(e._row(c,self.id)['status'],'In Development')
 def test_reminders_three(self):
  for day in ['2026-12-01','2026-12-01','2026-12-02','2026-12-02','2026-12-03','2026-12-04']:
   e.schedule_reminders(today=day)
  with e.db() as c:
   count=c.execute('SELECT COUNT(*) FROM reminders WHERE module_id=?',(self.id,)).fetchone()[0]
   self.assertEqual(count,3)
 def test_safe_default_no_network(self):
  import services as s
  with self.assertRaisesRegex(RuntimeError,'not configured'):s.ai_check('requirements','test')

if __name__=='__main__':unittest.main()
