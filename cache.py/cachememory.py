<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Cache Memory Mapping Simulator (Beginner Mode)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Flash/glow highlights for 1s */
    .flash-green { animation: flashGreen 1s ease-out; }
    .flash-red { animation: flashRed 1s ease-out; }
    .flash-yellow { animation: flashYellow 1s ease-out; }
    .flash-blue { animation: flashBlue 1s ease-out; }

    @keyframes flashGreen { 0% { background-color: #d1fae5; box-shadow: 0 0 0 0 rgba(16,185,129,0.5);} 50%{ box-shadow: 0 0 0 8px rgba(16,185,129,0.15);} 100% { background-color: white; box-shadow: 0 0 0 0 rgba(16,185,129,0);} }
    @keyframes flashRed { 0% { background-color: #fee2e2; box-shadow: 0 0 0 0 rgba(239,68,68,0.5);} 50%{ box-shadow: 0 0 0 8px rgba(239,68,68,0.15);} 100% { background-color: white; box-shadow: 0 0 0 0 rgba(239,68,68,0);} }
    @keyframes flashYellow { 0% { background-color: #fef3c7; box-shadow: 0 0 0 0 rgba(234,179,8,0.5);} 50%{ box-shadow: 0 0 0 8px rgba(234,179,8,0.15);} 100% { background-color: white; box-shadow: 0 0 0 0 rgba(234,179,8,0);} }
    @keyframes flashBlue { 0% { background-color: #dbeafe; box-shadow: 0 0 0 0 rgba(59,130,246,0.5);} 50%{ box-shadow: 0 0 0 8px rgba(59,130,246,0.15);} 100% { background-color: white; box-shadow: 0 0 0 0 rgba(59,130,246,0);} }

    /* Arrow animation layer */
    #arrowLayer { position: fixed; left: 0; top: 0; width: 100vw; height: 100vh; pointer-events: none; z-index: 50; }
    .arrow { position: fixed; height: 3px; background: #10b981; border-radius: 2px; width: 0; transform-origin: 0 50%; transition: width 1s ease; }
    .arrow::after { content: ""; position: absolute; right: -6px; top: -4px; border-left: 8px solid #10b981; border-top: 5px solid transparent; border-bottom: 5px solid transparent; }

    /* Status banner */
    #statusBanner { position: fixed; top: 16px; left: 50%; transform: translateX(-50%); z-index: 60; pointer-events: none; opacity: 0; transition: opacity 0.6s ease; }
    #statusBanner.show { opacity: 1; }
  </style>
</head>
<body class="bg-gray-50 text-gray-800 font-sans p-4">
  <div id="arrowLayer"></div>
  <div id="statusBanner" class="text-3xl font-extrabold drop-shadow-lg"></div>

  <!-- Top Bar -->
  <div class="flex flex-col md:flex-row justify-between items-center mb-4 gap-4">
    <h1 class="text-2xl font-bold">Cache Memory Mapping Simulator (Beginner Mode)</h1>
    <div class="flex gap-2 items-center">
      <select id="mappingType" class="border rounded p-2">
        <option value="direct">Direct Mapping</option>
        <option value="fully">Fully Associative</option>
        <option value="set">Set-Associative</option>
      </select>
      <input id="cacheSize" type="number" min="1" value="8" placeholder="Cache size (blocks)" class="border rounded p-2 w-44"/>
      <input id="blockSize" type="number" min="1" value="4" placeholder="Block size (bytes)" class="border rounded p-2 w-44"/>
      <input id="numSets" type="number" min="1" value="2" placeholder="Number of sets" class="border rounded p-2 w-44 hidden"/>
      <button id="startBtn" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded">Start Simulation</button>
      <button id="nextBtn" class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded">Next Step</button>
      <button id="resetBtn" class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded">Reset</button>
    </div>
  </div>

  <!-- Main Layout -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <!-- Left Panel: Address Breakdown -->
    <div class="bg-white rounded shadow p-4">
      <h2 class="text-lg font-semibold mb-2">Address Breakdown</h2>
      <div id="addressBinary" class="font-mono text-sm mb-2">Address: 0x00 → 00000000</div>
      <div class="flex flex-col gap-1 text-sm">
        <div class="text-blue-600">Tag bits: <span id="tagBits">--</span></div>
        <div class="text-purple-600">Index bits: <span id="indexBits">--</span></div>
        <div class="text-pink-600">Offset bits: <span id="offsetBits">--</span></div>
      </div>
    </div>

    <!-- Center Panel: Cache & Memory -->
    <div class="bg-white rounded shadow p-4">
      <h2 class="text-lg font-semibold mb-2">Cache & Memory</h2>
      <div id="cacheDisplay" class="mb-4 flex flex-col gap-2"></div>
      <div id="memoryDisplay" class="grid grid-cols-8 md:grid-cols-8 gap-2 text-center"></div>
    </div>

    <!-- Right Panel: Step Explanation -->
    <div class="bg-white rounded shadow p-4">
      <h2 class="text-lg font-semibold mb-2">Step Explanation</h2>
      <ol class="list-decimal list-inside text-sm space-y-1">
        <li>Convert address to binary</li>
        <li>Extract tag, index, offset</li>
        <li>Check cache set/line</li>
        <li>Compare tags</li>
        <li>Decide hit/miss</li>
        <li>Load block if miss (from memory → cache)</li>
        <li>Update cache and stats</li>
      </ol>
    </div>
  </div>

  <!-- Bottom Stats -->
  <div class="mt-6 text-center">
    <div>Hits: <span id="hitCount">0</span> | Misses: <span id="missCount">0</span> | Hit Rate: <span id="hitRate">0%</span></div>
  </div>

  <script>
    // Elements
    const mappingTypeEl = document.getElementById('mappingType');
    const numSetsEl = document.getElementById('numSets');
    const cacheSizeEl = document.getElementById('cacheSize');
    const blockSizeEl = document.getElementById('blockSize');
    const startBtn = document.getElementById('startBtn');
    const nextBtn = document.getElementById('nextBtn');
    const resetBtn = document.getElementById('resetBtn');

    const addressBinaryEl = document.getElementById('addressBinary');
    const tagBitsEl = document.getElementById('tagBits');
    const indexBitsEl = document.getElementById('indexBits');
    const offsetBitsEl = document.getElementById('offsetBits');

    const cacheDisplay = document.getElementById('cacheDisplay');
    const memoryDisplay = document.getElementById('memoryDisplay');
    const hitCountEl = document.getElementById('hitCount');
    const missCountEl = document.getElementById('missCount');
    const hitRateEl = document.getElementById('hitRate');
    const arrowLayer = document.getElementById('arrowLayer');
    const statusBanner = document.getElementById('statusBanner');

    // State
    let config = null;   // {mappingType, cacheSize, blockSize, numSets, linesPerSet, offsetBits, indexBits, tagBits}
    let cache = [];      // Array of sets -> lines
    let currentAddress = 0; // 8-bit address
    let hits = 0, misses = 0;

    mappingTypeEl.addEventListener('change', () => {
      numSetsEl.classList.toggle('hidden', mappingTypeEl.value !== 'set');
    });

    startBtn.addEventListener('click', startSimulation);
    nextBtn.addEventListener('click', nextStep);
    resetBtn.addEventListener('click', resetSimulation);

    function isPowerOfTwo(n){ return n > 0 && (n & (n - 1)) === 0; }

    function startSimulation() {
      const mappingType = mappingTypeEl.value;
      const cacheSize = parseInt(cacheSizeEl.value, 10);
      const blockSize = parseInt(blockSizeEl.value, 10);
      const numSets = mappingType === 'set' ? parseInt(numSetsEl.value, 10) : (mappingType === 'direct' ? cacheSize : 1);

      if (!isFinite(cacheSize) || !isFinite(blockSize) || !isFinite(numSets) || cacheSize <= 0 || blockSize <= 0 || numSets <= 0) {
        alert('Please enter valid positive numbers for all fields.'); return;
      }
      if (!isPowerOfTwo(blockSize)) { alert('Block size must be a power of two.'); return; }
      if (!isPowerOfTwo(cacheSize)) { alert('Cache size (in blocks) must be a power of two.'); return; }
      if (mappingType === 'set' && !isPowerOfTwo(numSets)) { alert('Number of sets must be a power of two for set-associative.'); return; }
      if (mappingType === 'set' && (cacheSize % numSets !== 0)) { alert('Cache size must be divisible by number of sets.'); return; }

      const linesPerSet = cacheSize / numSets; // integer by validation
      const offsetBits = Math.log2(blockSize) | 0;
      const indexBits = mappingType === 'fully' ? 0 : Math.log2(numSets) | 0;
      const tagBits = 8 - offsetBits - indexBits;
      if (tagBits < 0) { alert('Configuration too large for 8-bit address space.'); return; }

      config = { mappingType, cacheSize, blockSize, numSets, linesPerSet, offsetBits, indexBits, tagBits };

      // Initialize cache: sets x lines
      cache = Array.from({ length: numSets }, () =>
        Array.from({ length: linesPerSet }, () => ({ valid: false, tag: null, data: null, age: 0 }))
      );

      // Reset state and render
      hits = 0; misses = 0; currentAddress = 0;
      renderCache();
      renderMemory();
      updateAddressBits(0);
      updateStats();
    }

    function resetSimulation(){
      if (!config) { return; }
      startSimulation();
    }

    function renderCache(){
      if (!config) { cacheDisplay.innerHTML = ''; return; }
      const { numSets, linesPerSet } = config;
      cacheDisplay.innerHTML = '';
      for (let s = 0; s < numSets; s++) {
        const setWrap = document.createElement('div');
        setWrap.className = 'border rounded p-2';

        const title = document.createElement('div');
        title.className = 'text-sm text-gray-600 mb-2';
        title.textContent = Set ${s};
        setWrap.appendChild(title);

        for (let l = 0; l < linesPerSet; l++) {
          const line = cache[s][l];
          const row = document.createElement('div');
          row.id = cache-line-${s}-${l};
          row.className = 'grid grid-cols-12 gap-2 items-center text-sm border rounded px-2 py-1 bg-white';

          const colValid = document.createElement('div'); colValid.className = 'col-span-2'; colValid.textContent = line.valid ? '1' : '0';
          const colTag = document.createElement('div'); colTag.className = 'col-span-4 font-mono'; colTag.textContent = line.tag !== null ? line.tag.toString(2).padStart(config.tagBits, '0') : '--';
          const colData = document.createElement('div'); colData.className = 'col-span-6 truncate'; colData.textContent = line.data !== null ? line.data : '--';

          const labels = document.createElement('div'); labels.className = 'col-span-12 text-[11px] text-gray-500 -mt-1'; labels.textContent = '[Valid] [Tag] [Data]';

          row.appendChild(colValid);
          row.appendChild(colTag);
          row.appendChild(colData);
          row.appendChild(labels);
          setWrap.appendChild(row);
        }
        cacheDisplay.appendChild(setWrap);
      }
    }

    function renderMemory(){
      if (!config) { memoryDisplay.innerHTML = ''; return; }
      const { blockSize } = config;
      const blocks = 256 / blockSize; // 8-bit address space
      memoryDisplay.innerHTML = '';
      for (let i = 0; i < blocks; i++) {
        const cell = document.createElement('div');
        cell.id = mem-block-${i};
        cell.className = 'border rounded p-2 bg-white text-xs select-none';
        const addr = (i * blockSize) & 0xff;
        cell.textContent = '0x' + addr.toString(16).padStart(2, '0');
        memoryDisplay.appendChild(cell);
      }
    }

    function updateAddressBits(address){
      if (!config) return;
      const { offsetBits, indexBits, tagBits } = config;
      const bin = address.toString(2).padStart(8, '0');
      addressBinaryEl.textContent = Address: 0x${address.toString(16).padStart(2,'0')} → ${bin};
      const tag = bin.slice(0, tagBits) || '--';
      const index = indexBits ? bin.slice(tagBits, tagBits + indexBits) : '--';
      const offset = bin.slice(tagBits + indexBits) || '--';
      tagBitsEl.textContent = tag;
      indexBitsEl.textContent = index;
      offsetBitsEl.textContent = offset;
    }

    function updateStats(){
      const total = hits + misses;
      hitCountEl.textContent = String(hits);
      missCountEl.textContent = String(misses);
      hitRateEl.textContent = total === 0 ? '0%' : ${Math.round((hits/total)*100)}%;
    }

    function addFlash(el, cls){ if (!el) return; el.classList.remove('flash-green','flash-red','flash-yellow','flash-blue'); void el.offsetWidth; el.classList.add(cls); setTimeout(() => el.classList.remove(cls), 1000); }

    function showBanner(hit){
      statusBanner.textContent = hit ? 'HIT ✅' : 'MISS ❌';
      statusBanner.classList.remove('text-red-600','text-green-600');
      statusBanner.classList.add(hit ? 'text-green-600' : 'text-red-600');
      statusBanner.classList.add('show');
      setTimeout(() => { statusBanner.classList.remove('show'); }, 1000); // show for 1s then fade via CSS transition
    }

    function animateTransfer(fromEl, toEl){
      if (!fromEl || !toEl) return;
      const fr = fromEl.getBoundingClientRect();
      const tr = toEl.getBoundingClientRect();
      const fx = fr.left + fr.width/2;
      const fy = fr.top + fr.height/2;
      const tx = tr.left + tr.width/2;
      const ty = tr.top + tr.height/2;
      const dx = tx - fx; const dy = ty - fy;
      const angle = Math.atan2(dy, dx);
      const length = Math.sqrt(dx*dx + dy*dy);
      const arrow = document.createElement('div');
      arrow.className = 'arrow';
      arrow.style.left = fx + 'px';
      arrow.style.top = fy + 'px';
      arrow.style.transform = rotate(${angle}rad);
      arrowLayer.appendChild(arrow);
      requestAnimationFrame(() => { arrow.style.width = length + 'px'; });
      setTimeout(() => { arrow.remove(); }, 1100);
    }

    function nextStep(){
      if (!config) { alert('Click Start Simulation first.'); return; }
      const { mappingType, blockSize, numSets, linesPerSet, offsetBits, indexBits } = config;

      const address = currentAddress & 0xff;
      const blockIndex = address >> offsetBits; // which memory block
      const setIndex = indexBits ? (blockIndex & ((1 << indexBits) - 1)) : 0;
      const tag = blockIndex >> indexBits;

      // Update left panel
      updateAddressBits(address);

      // Memory highlight for the block touched this step
      const memEl = document.getElementById(mem-block-${blockIndex});
      addFlash(memEl, 'flash-blue');

      // Search the set for hit
      const set = cache[setIndex];
      let hit = false; let lineIdx = -1; let replaced = false; let victimIdx = -1;

      for (let i = 0; i < set.length; i++) {
        if (set[i].valid && set[i].tag === tag) { hit = true; lineIdx = i; break; }
      }

      if (hit) {
        hits++;
        // Aging for LRU
        for (let i = 0; i < set.length; i++) set[i].age++;
        set[lineIdx].age = 0;
        const lineEl = document.getElementById(cache-line-${setIndex}-${lineIdx});
        addFlash(lineEl, 'flash-green');
        showBanner(true);
      } else {
        misses++;
        // Find victim: first invalid else LRU (max age)
        for (let i = 0; i < set.length; i++) { if (!set[i].valid) { victimIdx = i; break; } }
        if (victimIdx === -1) {
          let maxAge = -1; for (let i = 0; i < set.length; i++) { if (set[i].age > maxAge) { maxAge = set[i].age; victimIdx = i; } }
          replaced = true;
        }
        // Aging and place new block
        for (let i = 0; i < set.length; i++) set[i].age++;
        const dataLabel = Block ${blockIndex} @ 0x${(blockIndex*blockSize & 0xff).toString(16).padStart(2,'0')};
        set[victimIdx] = { valid: true, tag, data: dataLabel, age: 0 };

        // Animate memory -> cache arrow
        const lineEl = document.getElementById(cache-line-${setIndex}-${victimIdx});
        animateTransfer(memEl, lineEl);
        addFlash(lineEl, replaced ? 'flash-yellow' : 'flash-red');
        showBanner(false);
      }

      // Re-render only changed rows for simplicity we re-render whole cache
      renderCache();
      updateStats();

      // Next address (simple stepping by block size within 8-bit space)
      currentAddress = (currentAddress + blockSize) & 0xff;
    }

    // Initialize default view
    startSimulation();
  </script>
</body>
</html>