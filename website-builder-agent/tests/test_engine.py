import os,tempfile,importlib,unittest
os.environ['DATABASE_PATH']=tempfile.mktemp(suffix='.sqlite3')
import engine as e
class WorkflowTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):e.init_db()
 def test_01_review_requires_all_and_no_block(self):
  e.add_artifact(1,'design_system','Approved tokens')
  e.set_step(2)
  e.add_member('PM','pm@example.com')
  e.add_member('Designer','designer@example.com')
  e.add_artifact(2,'requirements','https://docs.example/doc')
  e.create_round(2,'https://docs.example/doc')
  with e.connection() as c:
   r=e.review(c,2);rid=r['id'];m=[x['id'] for x in c.execute('SELECT id FROM members').fetchall()]
  e.respond(rid,m[0],'approved','fine')
  with self.assertRaises(ValueError):e.set_step(3)
  e.respond(rid,m[1],'changes_requested','Fix content')
  with self.assertRaises(ValueError):e.set_step(3)
  e.respond(rid,m[1],'no_objection','Resolved by PM')
  e.set_step(3)
  with e.connection() as c:self.assertEqual(e.project(c)['step'],3)
 def test_02_reminders_max_3_and_no_double_advance(self):
  with e.connection() as c:
   rid=c.execute('SELECT id FROM rounds ORDER BY id DESC LIMIT 1').fetchone()['id']
   with self.assertRaises(ValueError):e.reminder_candidates(c,rid)
  with self.assertRaises(ValueError):e.set_step(4)
if __name__=='__main__':unittest.main()
