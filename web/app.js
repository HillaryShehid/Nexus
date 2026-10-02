const messages=document.querySelector("#messages"),form=document.querySelector("#chat-form"),input=document.querySelector("#input"),statusEl=document.querySelector("#status"),dot=document.querySelector(".dot"),mic=document.querySelector("#mic"),voiceStatus=document.querySelector("#voice-status"),speakToggle=document.querySelector("#speak-toggle");let speakResponses=false,recognition=null;

function addMessage(who,text){const el=document.createElement("div");el.className="message "+(who==="You"?"user":"nexus");const label=document.createElement("div");label.className="label";label.textContent=who==="You"?"YOU":"NEXUS";el.append(label,document.createTextNode(text));messages.appendChild(el);messages.scrollTop=messages.scrollHeight;return el}

async function checkHealth(){try{const r=await fetch("/api/health");if(!r.ok)throw new Error();const data=await r.json();statusEl.textContent=data.ok?"Online":"Unavailable";dot.classList.toggle("online",!!data.ok)}catch{statusEl.textContent="Backend offline";dot.classList.remove("online")}}
checkHealth();

form.addEventListener("submit",async e=>{e.preventDefault();const text=input.value.trim();if(!text)return;input.value="";addMessage("You",text);const pending=addMessage("Nexus","Thinking…");try{const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text})});const data=await r.json();if(!r.ok)throw new Error(data.error||"Request failed");pending.lastChild.textContent=data.response||"I didn't receive a response.";if(speakResponses)speak(data.response||"");}catch(err){pending.lastChild.textContent="I couldn't reach the Nexus brain. Make sure the local Nexus server is running.";console.error(err)}});

function speak(text){if(!("speechSynthesis"in window)){voiceStatus.textContent="Voice output unavailable in this browser";return}speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.rate=.98;u.pitch=.95;speechSynthesis.speak(u)}

speakToggle.addEventListener("click",()=>{speakResponses=!speakResponses;speakToggle.textContent=speakResponses?"🔊 Read responses aloud: ON":"🔊 Read responses aloud";voiceStatus.textContent=speakResponses?"Voice output: on":"Voice: ready"});

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SR){recognition=new SR();recognition.lang="en-CA";recognition.interimResults=false;recognition.continuous=false;recognition.onstart=()=>{voiceStatus.textContent="Listening…";mic.textContent="⏺️"};recognition.onend=()=>{voiceStatus.textContent="Voice: ready";mic.textContent="🎙️"};recognition.onerror=()=>{voiceStatus.textContent="Voice input error";mic.textContent="🎙️"};recognition.onresult=e=>{input.value=e.results[0][0].transcript;input.focus()};mic.addEventListener("click",()=>recognition.start())}else{mic.disabled=true;mic.title="Speech recognition is not supported in this browser";voiceStatus.textContent="Voice input unavailable in this browser"}
