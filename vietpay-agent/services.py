"""Opt-in outgoing integrations. No automatic sending or publishing."""
import os, smtplib, ssl
from email.message import EmailMessage
import httpx

async def generate_concept(provider, brief):
 system=('You are a senior Vietnamese fintech web UX strategist. Produce one independently reasoned website concept with sitemap, audiences, page-level requirements, conversion paths, wireframe text, accessibility and measurable acceptance criteria. Distinguish approved facts from TBD. Do not fabricate partner, pricing or performance claims. Make this ready to reconstruct in Figma. Reference supplied design system and requirements only.')
 if provider=='gpt':
  key=os.getenv('OPENAI_API_KEY')
  if not key: raise ValueError('OPENAI_API_KEY is missing')
  async with httpx.AsyncClient(timeout=120) as client:
   r=await client.post('https://api.openai.com/v1/chat/completions',headers={'Authorization':f'Bearer {key}'},json={'model':os.getenv('OPENAI_MODEL','gpt-4.1'),'messages':[{'role':'system','content':system},{'role':'user','content':brief}],'temperature':0.7})
   r.raise_for_status();return r.json()['choices'][0]['message']['content']
 if provider=='claude':
  key=os.getenv('ANTHROPIC_API_KEY')
  if not key: raise ValueError('ANTHROPIC_API_KEY is missing')
  async with httpx.AsyncClient(timeout=120) as client:
   r=await client.post('https://api.anthropic.com/v1/messages',headers={'x-api-key':key,'anthropic-version':'2023-06-01'},json={'model':os.getenv('ANTHROPIC_MODEL','claude-sonnet-4-5'),'max_tokens':3500,'system':system,'messages':[{'role':'user','content':brief}]})
   r.raise_for_status();return ''.join(x.get('text','') for x in r.json()['content'])
 raise ValueError('provider must be gpt or claude')

def send_email(address,subject,body):
 host=os.getenv('SMTP_HOST');user=os.getenv('SMTP_USER');pw=os.getenv('SMTP_PASSWORD');sender=os.getenv('SMTP_FROM')
 if not all([host,user,pw,sender]):raise ValueError('SMTP variables missing; no message sent')
 msg=EmailMessage();msg['From']=sender;msg['To']=address;msg['Subject']=subject;msg.set_content(body)
 with smtplib.SMTP(host,int(os.getenv('SMTP_PORT','587')),timeout=20) as smtp:
  smtp.starttls(context=ssl.create_default_context());smtp.login(user,pw);smtp.send_message(msg)

async def send_chat(message):
 url=os.getenv('GOOGLE_CHAT_WEBHOOK')
 if not url: raise ValueError('GOOGLE_CHAT_WEBHOOK missing')
 async with httpx.AsyncClient(timeout=15) as client:
  r=await client.post(url,json={'text':message});r.raise_for_status()
