(() => {
  const island = document.getElementById('island');
  const sceneCanvas = document.getElementById('scene');
  const statusText = document.getElementById('statusText');
  const compactStatus = document.getElementById('compactStatus');
  const meterLabel = document.getElementById('meterLabel');
  const bars = [...document.querySelectorAll('#meter i')];
  const micButton = document.getElementById('micButton');
  const closeButton = document.getElementById('closeButton');
  const stateLabels = {idle:'SYSTEM ONLINE', listening:'LISTENING / AUDIO INPUT', thinking:'THINKING / PROCESSING', speaking:'SPEAKING / RESPONSE'};
  let expanded = false, status = 'idle', audioLevel = 0, micStream = null, analyser = null, audioData = null;
  let renderer, scene, camera, core, coreGlow, ringGroup, particles, clock;
  let resizeTimer = null;

  function bridgeResize(value) {
    expanded = value;
    island.classList.toggle('expanded', value);
    if (window.pywebview && window.pywebview.api) {
      try { window.pywebview.api.resize(value); } catch (_) {}
    }
    setTimeout(resizeRenderer, 90);
  }
  // Keep the pill compact.
  closeButton.addEventListener('click', () => {
    if (window.pywebview && window.pywebview.api) window.pywebview.api.close();
  });
  document.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    if (window.pywebview && window.pywebview.api) window.pywebview.api.close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && window.pywebview && window.pywebview.api) window.pywebview.api.close();
  });

  function setStatus(next) {
    if (!stateLabels[next]) next = 'idle';
    status = next;
    island.dataset.status = next;
    statusText.textContent = stateLabels[next];
    compactStatus.textContent = stateLabels[next];
    meterLabel.textContent = next === 'listening' ? 'MIC INPUT ACTIVE' : next === 'speaking' ? 'VOICE OUTPUT ACTIVE' : 'AUDIO LINK READY';
  }
  window.NovaUI = { setStatus };

  function initThree() {
    if (!window.THREE) {
      compactStatus.textContent = '3D ENGINE UNAVAILABLE';
      return;
    }
    const THREE = window.THREE;
    renderer = new THREE.WebGLRenderer({canvas: sceneCanvas, alpha:true, antialias:true, powerPreference:'high-performance'});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(37, 2, .1, 100);
    camera.position.set(0, 0, 7.4);
    clock = new THREE.Clock();
    scene.add(new THREE.AmbientLight(0x6288ff, 1.35));
    const cyanLight = new THREE.PointLight(0x15dfff, 4.5, 12); cyanLight.position.set(-2.4, 1.5, 3); scene.add(cyanLight);
    const violetLight = new THREE.PointLight(0x9850ff, 4.2, 12); violetLight.position.set(2.4, -1.3, 2); scene.add(violetLight);

    const orb = new THREE.Group(); scene.add(orb); core = orb;
    const geo = new THREE.IcosahedronGeometry(.69, 5);
    const mat = new THREE.MeshPhysicalMaterial({color:0x0c8fb7, emissive:0x063b69, emissiveIntensity:1.25, metalness:.42, roughness:.19, clearcoat:1, clearcoatRoughness:.14, transmission:.08});
    const sphere = new THREE.Mesh(geo, mat); orb.add(sphere);
    const inner = new THREE.Mesh(new THREE.IcosahedronGeometry(.51, 4), new THREE.MeshBasicMaterial({color:0x38e6ff, wireframe:true, transparent:true, opacity:.18})); orb.add(inner);
    coreGlow = new THREE.Mesh(new THREE.SphereGeometry(.88, 32, 32), new THREE.MeshBasicMaterial({color:0x087dff, transparent:true, opacity:.09, side:THREE.BackSide})); orb.add(coreGlow);

    ringGroup = new THREE.Group(); scene.add(ringGroup);
    const ringSpecs = [
      {r:1.12, tube:.012, color:0x31e8ff, rx:1.04, ry:.18, rz:.12},
      {r:1.35, tube:.008, color:0x8c55ff, rx:.28, ry:1.0, rz:.45},
      {r:1.55, tube:.007, color:0x358cff, rx:.83, ry:.25, rz:-.62},
      {r:.96, tube:.006, color:0xa45bff, rx:.48, ry:.86, rz:.95}
    ];
    ringSpecs.forEach((spec, i) => {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(spec.r, spec.tube, 8, 180), new THREE.MeshBasicMaterial({color:spec.color, transparent:true, opacity:i===0?.88:.65}));
      ring.rotation.set(spec.rx, spec.ry, spec.rz); ring.userData.spin = (i%2 ? -1 : 1) * (.12 + i*.025); ringGroup.add(ring);
      const bead = new THREE.Mesh(new THREE.SphereGeometry(.035, 12, 12), new THREE.MeshBasicMaterial({color:spec.color}));
      bead.position.set(spec.r, 0, 0); ring.add(bead);
    });
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(180*3);
    for (let i=0;i<180;i++) {
      const radius=1.65+Math.random()*1.25, a=Math.random()*Math.PI*2;
      positions[i*3]=Math.cos(a)*radius; positions[i*3+1]=(Math.random()-.5)*2.0; positions[i*3+2]=(Math.random()-.5)*.8;
    }
    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions,3));
    particles = new THREE.Points(particleGeo, new THREE.PointsMaterial({color:0x64dfff,size:.018,transparent:true,opacity:.65,depthWrite:false})); scene.add(particles);
    resizeRenderer(); animate();
  }

  function resizeRenderer() {
    if (!renderer || !sceneCanvas) return;
    const rect = island.getBoundingClientRect();
    const width = Math.max(1, rect.width), height = Math.max(1, rect.height);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resizeRenderer);

  function animate() {
    if (!renderer) return;
    requestAnimationFrame(animate);
    const t = clock.getElapsedTime();
    const listeningBoost = status === 'listening' ? audioLevel : 0;
    const speakingPulse = status === 'speaking' ? .5 + .5*Math.sin(t*12) : 0;
    const energy = Math.max(listeningBoost, speakingPulse*.42, status === 'thinking' ? .22 : 0);
    core.rotation.y = t*(status==='thinking'?.75:.24);
    core.rotation.x = Math.sin(t*.35)*.12;
    const pulse = 1 + Math.sin(t*(status==='idle'?1.1:3.8))*(status==='idle'?.025:.035) + energy*.11;
    core.scale.setScalar(pulse);
    coreGlow.material.opacity = .07 + energy*.17 + (Math.sin(t*1.6)+1)*.018;
    ringGroup.rotation.y = t*.13;
    ringGroup.rotation.x = Math.sin(t*.23)*.1;
    ringGroup.children.forEach((ring) => { ring.rotation.z += ring.userData.spin*.008*(status==='thinking'?2.0:1); });
    particles.rotation.y = -t*.025;
    particles.rotation.x = Math.sin(t*.18)*.08;
    camera.position.x = Math.sin(t*.17)*.035;
    camera.lookAt(0,0,0);
    renderer.render(scene,camera);
    bars.forEach((bar,i) => {
      const wave = Math.abs(Math.sin(t*3.7+i*.67));
      const live = status==='listening' ? audioLevel*(.45+wave) : status==='speaking' ? speakingPulse*(.35+wave) : status==='thinking' ? .12+wave*.16 : .08+wave*.08;
      bar.style.height = `${3+Math.min(1,live)*13}px`;
      bar.style.opacity = `${.35+Math.min(1,live)*.65}`;
    });
  }

  async function enableMicMeter() {
    try {
      if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
        micStream = null; analyser = null; audioData = null; audioLevel = 0;
        micButton.title = 'Enable live microphone visualizer';
        meterLabel.textContent = 'AUDIO LINK READY';
        return;
      }
      micStream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}, video:false});
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const audioContext = new AudioContextClass();
      const source = audioContext.createMediaStreamSource(micStream);
      analyser = audioContext.createAnalyser(); analyser.fftSize = 256;
      audioData = new Uint8Array(analyser.frequencyBinCount); source.connect(analyser);
      micButton.title = 'Disable live microphone visualizer';
      meterLabel.textContent = 'LIVE MIC LEVEL';
      sampleMic();
    } catch (err) {
      meterLabel.textContent = 'MIC VISUALIZER UNAVAILABLE';
      console.warn('Microphone visualizer unavailable:', err);
    }
  }
  function sampleMic() {
    if (!analyser || !audioData) return;
    analyser.getByteTimeDomainData(audioData);
    let sum=0;
    for (let i=0;i<audioData.length;i++) { const v=(audioData[i]-128)/128; sum += v*v; }
    const rms=Math.sqrt(sum/audioData.length);
    audioLevel = Math.min(1, rms*5.5);
    requestAnimationFrame(sampleMic);
  }
  micButton.addEventListener('click', (event) => { event.stopPropagation(); enableMicMeter(); });

  // The bridge is ready once pywebview exposes its API. Read Python's current state too.
  window.addEventListener('pywebviewready', async () => {
    try { setStatus(await window.pywebview.api.get_status()); } catch (_) {}
  });
  initThree();
  setStatus('idle');
})();
