import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Message = { id: string; role: 'user' | 'assistant'; text: string };
type Status = 'idle' | 'connecting' | 'listening' | 'speaking' | 'error';
const names: Record<Status,string> = {idle:'Sẵn sàng',connecting:'Đang kết nối',listening:'Đang nghe',speaking:'AI đang nói',error:'Lỗi kết nối'};

function App() {
  const [status,setStatus] = useState<Status>('idle');
  const [muted,setMuted] = useState(false);
  const [messages,setMessages] = useState<Message[]>([]);
  const [error,setError] = useState('');
  const pc = useRef<RTCPeerConnection|null>(null);
  const mic = useRef<MediaStream|null>(null);
  const audio = useRef<HTMLAudioElement|null>(null);
  const dc = useRef<RTCDataChannel|null>(null);
  const sequence = useRef(0);

  function add(id:string,role:Message['role'],text:string,append=false) {
    setMessages(old => {
      const index=old.findIndex(m=>m.id===id);
      if(index<0)return [...old,{id,role,text}];
      return old.map((m,i)=>i===index?{...m,text:append?m.text+text:text}:m);
    });
  }
  function handleEvent(event:MessageEvent) {
    let e:any; try {e=JSON.parse(event.data);} catch {return;}
    switch(e.type) {
      case 'input_audio_buffer.speech_started':setStatus('listening');break;
      case 'response.created':setStatus('speaking');break;
      case 'response.output_audio_transcript.delta':
      case 'response.audio_transcript.delta':
        add(e.item_id||e.response_id||'current','assistant',e.delta||'',true);break;
      case 'response.output_audio_transcript.done':
      case 'response.audio_transcript.done':
        if(e.transcript)add(e.item_id||e.response_id||'current','assistant',e.transcript);break;
      case 'conversation.item.input_audio_transcription.completed':
        add(e.item_id||crypto.randomUUID(),'user',e.transcript||'');break;
      case 'response.done':setStatus('listening');break;
      case 'error':setError(e.error?.message||'Realtime API error');break;
    }
  }
  function cleanup() {
    sequence.current++;
    dc.current?.close();dc.current=null;
    pc.current?.close();pc.current=null;
    mic.current?.getTracks().forEach(t=>t.stop());mic.current=null;
    if(audio.current){audio.current.pause();audio.current.srcObject=null;audio.current.remove();audio.current=null;}
  }
  function stop(){cleanup();setStatus('idle');setMuted(false);}
  useEffect(()=>()=>cleanup(),[]);
  async function start(){
    if(status==='connecting')return;
    const seq=++sequence.current;
    setStatus('connecting');setError('');setMessages([]);setMuted(false);
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
      if(seq!==sequence.current){stream.getTracks().forEach(t=>t.stop());return;}
      mic.current=stream;
      const r=await fetch('/api/session',{method:'POST'});
      const secret=await r.json().catch(()=>({}));
      if(!r.ok)throw new Error(secret.message||'Session creation failed');
      if(seq!==sequence.current)return;
      const peer=new RTCPeerConnection();pc.current=peer;
      const output=document.createElement('audio');output.autoplay=true;audio.current=output;
      peer.ontrack=e=>{output.srcObject=e.streams[0];void output.play().catch(()=>setError('Không thể phát âm thanh'));};
      peer.onconnectionstatechange=()=>{
        if(['failed','disconnected'].includes(peer.connectionState)){
          setError('Mất kết nối. Kết thúc và thử lại.');setStatus('error');
        }
      };
      stream.getTracks().forEach(t=>peer.addTrack(t,stream));
      const channel=peer.createDataChannel('oai-events');dc.current=channel;channel.onmessage=handleEvent;
      const offer=await peer.createOffer();await peer.setLocalDescription(offer);
      const answer=await fetch('https://api.openai.com/v1/realtime/calls',{
        method:'POST',headers:{Authorization:`Bearer ${secret.value}`,'Content-Type':'application/sdp'},body:offer.sdp
      });
      if(!answer.ok)throw new Error(`WebRTC handshake failed: ${answer.status}`);
      if(seq!==sequence.current)return;
      await peer.setRemoteDescription({type:'answer',sdp:await answer.text()});
      if(seq!==sequence.current)return;
      setStatus('listening');
    }catch(e){
      if(seq!==sequence.current)return;
      cleanup();setStatus('error');setError(e instanceof Error?e.message:'Unknown error');
    }
  }
  function toggleMute(){
    if(!mic.current)return;
    mic.current.getAudioTracks().forEach(t=>t.enabled=muted);
    setMuted(!muted);
  }
  const connected=status==='listening'||status==='speaking'||status==='error'&&!!pc.current;
  return <main className="app">
    <header><h1>Voice AI <small>MVP</small></h1><p>OpenAI Realtime · WebRTC · React · NestJS</p></header>
    <section className="voice">
      <div className={'pulse '+status} aria-hidden="true">🎙</div>
      <strong>{names[status]}</strong>
      <p>Nói trực tiếp với AI; có thể chen ngang khi AI đang trả lời.</p>
      <div className="buttons">
        {connected?<button className="stop" onClick={stop}>Kết thúc</button>:<button disabled={status==='connecting'} onClick={start}>Bắt đầu</button>}
        <button className="secondary" disabled={!connected} onClick={toggleMute}>{muted?'Bật mic':'Tắt mic'}</button>
      </div>
      {error&&<p role="alert" className="error">{error}</p>}
    </section>
    <section className="transcript"><h2>Nội dung hội thoại</h2>
      {messages.length===0?<p className="empty">Hội thoại sẽ hiển thị tại đây.</p>:
      <div aria-live="polite">{messages.map(m=><article key={m.id} className={m.role}><b>{m.role==='user'?'Bạn':'AI'}</b><p>{m.text}</p></article>)}</div>}
    </section>
    <footer>Demo chạy local · Không đưa API key vào frontend</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
