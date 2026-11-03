(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const pct = (p) => `${Math.round(p * 100)}%`;
  const ms = (v) => (v < 1 ? "Dưới 1 mili giây" : `${Math.round(v).toLocaleString("vi-VN")} mili giây`);

  /* ---------- Phần đầu: ảnh hiện dần theo cột, các cột trôi lệch nhịp khi cuộn ---------- */
  const hero = $(".hero");
  $$(".col", hero).forEach((col, c) => {
    $$(".frame, .panel", col).forEach((el, r) => {
      el.style.setProperty("--d", `${c * 70 + r * 90}ms`);
      el.querySelector(".media")?.style.setProperty("--drift", `${-(c * 3 + r * 5)}s`);
    });
  });
  requestAnimationFrame(() => hero.classList.add("in"));
  setTimeout(() => hero.classList.add("in"), 300);

  const cols = $$(".col", hero);
  const speeds = [0.12, -0.06, 0, -0.1, 0.08];
  let ticking = false;
  function parallax() {
    ticking = false;
    if (innerWidth <= 760) return;
    const y = Math.min(scrollY, innerHeight);
    cols.forEach((col, i) => { col.style.transform = `translateY(${y * speeds[i]}px)`; });
  }
  if (!reduce) {
    addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(parallax); } }, { passive: true });
  }

  /* ---------- Từng phần của mỗi mục hiện ra theo thứ tự đọc ---------- */
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      e.target.classList.add("in");
      io.unobserve(e.target);
    });
  }, { rootMargin: "0px 0px -12% 0px" });

  $$("section").forEach((sec) => {
    $$("[data-reveal]", sec).forEach((el, i) => { el.style.setProperty("--d", `${i * 80}ms`); io.observe(el); });
  });
  $$(".seg").forEach((el, i) => el.style.setProperty("--d", `${i * 140}ms`));
  io.observe($(".bar"));

  const chart = $("[data-chart]");
  $$(".b", chart).forEach((el, i) => el.style.setProperty("--d", `${i * 45}ms`));
  io.observe(chart);

  // Con số độ tự tin trung bình lăn lên một lần
  const avgEl = $("[data-avg]");
  const avgTarget = Number(avgEl.textContent);
  if (!reduce && avgTarget) {
    avgEl.textContent = "0";
    new IntersectionObserver((entries, obs) => {
      if (!entries[0].isIntersecting) return;
      obs.disconnect();
      const t0 = performance.now();
      const step = (t) => {
        const k = Math.min(1, (t - t0) / 1400);
        avgEl.textContent = Math.round(avgTarget * (1 - Math.pow(1 - k, 3)));
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }).observe(avgEl);
  }

  /* ---------- Thanh bốn chặng: độ dài từng khúc là thời gian đo thật ---------- */
  const clauses = Object.fromEntries($$("[data-stage-clause]").map((p) => [p.dataset.stageClause, p]));
  $$(".seg").forEach((seg) => seg.setAttribute("data-clause", clauses[seg.dataset.stage].textContent));

  function setStages(t) {
    Object.entries(t).forEach(([stage, v]) => {
      const seg = $(`.seg[data-stage="${stage}"]`);
      if (!seg || v == null) return;
      const grow = Math.max(v, 0.5).toFixed(2);
      seg.style.setProperty("--grow", grow);
      clauses[stage].style.setProperty("--grow", grow);
      $("[data-time]", seg).textContent = ms(v);
    });
  }

  /* ---------- Grad-CAM: phóng lưới 7 × 7 thành bản đồ nhiệt phủ lên ảnh ---------- */
  // Thang màu: giá trị thấp trong suốt, lên dần vàng rồi đỏ
  const CAM_STOPS = [
    [0, [37, 111, 130, 0]],
    [0.35, [37, 111, 130, 0.18]],
    [0.6, [255, 196, 0, 0.55]],
    [1, [220, 38, 38, 0.85]],
  ];
  function camColor(t) {
    for (let i = 1; i < CAM_STOPS.length; i++) {
      const [t1, c1] = CAM_STOPS[i];
      const [t0, c0] = CAM_STOPS[i - 1];
      if (t <= t1) {
        const k = (t - t0) / (t1 - t0);
        return c0.map((v, j) => v + (c1[j] - v) * k);
      }
    }
    return CAM_STOPS[CAM_STOPS.length - 1][1];
  }

  function drawCam(canvas, cam, aspect) {
    const rows = cam.length;
    const cols = cam[0].length;
    const small = document.createElement("canvas");
    small.width = cols;
    small.height = rows;
    const sctx = small.getContext("2d");
    const img = sctx.createImageData(cols, rows);
    cam.forEach((row, y) => row.forEach((v, x) => {
      const [r, g, b, a] = camColor(v);
      img.data.set([r, g, b, Math.round(a * 255)], (y * cols + x) * 4);
    }));
    sctx.putImageData(img, 0, 0);
    // Mô hình nhìn ảnh đã bị ép về hình vuông, nên lưới được kéo giãn theo đúng tỉ lệ ảnh gốc
    canvas.width = 320;
    canvas.height = Math.max(1, Math.round(320 / aspect));
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(small, 0, 0, canvas.width, canvas.height);
  }

  $$(".hero canvas.cam").forEach((c) => drawCam(c, JSON.parse(c.dataset.cam), Number(c.dataset.aspect)));
  const heroCamBtn = $("[data-hero-cam]");
  heroCamBtn.addEventListener("click", () => {
    const on = hero.classList.toggle("show-cam");
    heroCamBtn.setAttribute("aria-pressed", String(on));
    heroCamBtn.textContent = on ? "Ẩn Grad-CAM" : "Hiện Grad-CAM trên ảnh";
  });

  /* ---------- Bảng thử trực tiếp ---------- */
  const view = $("[data-drop]");
  const figure = $("[data-figure]");
  const preview = $("[data-preview]");
  const status = $("[data-status]");
  const rows = Object.fromEntries($$("[data-rows] li").map((li) => [li.dataset.cls, li]));

  const demoCam = $("[data-demo-cam]");
  const camControls = $("[data-cam-controls]");
  const camOn = $("[data-cam-on]");
  const camOpacity = $("[data-cam-opacity]");
  const applyCamControls = () => {
    figure.style.setProperty("--cam-opacity", camOn.checked ? camOpacity.value / 100 : 0);
    camOpacity.disabled = !camOn.checked;
  };
  camOn.addEventListener("change", applyCamControls);
  camOpacity.addEventListener("input", applyCamControls);
  applyCamControls();

  function showCam(r) {
    // Bản tĩnh (ONNX) chỉ có điểm số, không có gradient, nên ẩn phần Grad-CAM
    camControls.hidden = !r.cam;
    demoCam.hidden = !r.cam;
    if (!r.cam) return;
    const aspect = (preview.naturalWidth || 4) / (preview.naturalHeight || 3);
    drawCam(demoCam, r.cam, aspect);
    $("[data-cam-label]").textContent = r.label_vi;
  }

  function showResult(r) {
    if (preview.complete) showCam(r);
    else preview.addEventListener("load", () => showCam(r), { once: true });
    $("[data-verdict]").textContent = r.label_vi;
    $("[data-verdict-pct]").textContent = pct(r.confidence);
    r.probs.forEach(({ label, p }) => {
      const li = rows[label];
      li.querySelector(".val").textContent = pct(p);
      li.querySelector(".fill").style.setProperty("--p", p.toFixed(4));
      li.classList.toggle("top", label === r.label);
    });
  }

  function shutter() {
    figure.classList.remove("shutter");
    void figure.offsetWidth;
    figure.classList.add("shutter");
  }

  function addMine(r) {
    const bar = $("[data-mine]");
    bar.style.setProperty("--h", r.confidence.toFixed(3));
    bar.tabIndex = 0;
    $("[data-mine-val]", bar).textContent = `Của bạn ${pct(r.confidence)}`;
    $("[data-mine-tip]", bar).textContent = `Ảnh của bạn: ${r.label_vi} ${pct(r.confidence)}`;
  }

  /* ---------- Hai cách dự đoán: gửi lên máy chủ Python, hoặc chạy ONNX ngay trong trình duyệt ---------- */
  // Bản tĩnh (Vercel) đặt window.VEHICLE_MODEL; bản chạy bằng app.py thì không
  const local = window.VEHICLE_MODEL;

  async function predictOnServer(file, name) {
    const body = new FormData();
    body.append("file", file, name);
    const t0 = performance.now();
    const res = await fetch("/api/predict", { method: "POST", body });
    const total = performance.now() - t0;
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Máy chủ không trả lời.");
    const t = data.timings_ms;
    t.upload = Math.max(total - t.preprocess - t.inference - t.softmax, 0);
    return data;
  }

  let session = null;
  function loadSession() {
    if (!session) {
      ort.env.wasm.wasmPaths = local.wasm;
      ort.env.wasm.numThreads = 1;
      session = ort.InferenceSession.create(local.url, { executionProviders: ["wasm"] });
      session.catch(() => { session = null; });
    }
    return session;
  }

  // Giống app.py: thu nhỏ về tối đa 448 px (giữ tỉ lệ), rồi ép về 224 × 224 và chuẩn hoá theo ImageNet
  const MEAN = [0.485, 0.456, 0.406];
  const STD = [0.229, 0.224, 0.225];
  // Hệ số lọc tam giác theo cách PIL làm khi thu nhỏ BILINEAR (torchvision Resize dùng đúng phép này)
  function resizeCoeffs(inSize, outSize) {
    const scale = inSize / outSize;
    const support = Math.max(scale, 1);
    const result = [];
    for (let i = 0; i < outSize; i++) {
      const center = (i + 0.5) * scale;
      const lo = Math.max(Math.floor(center - support), 0);
      const hi = Math.min(Math.ceil(center + support), inSize);
      const w = [];
      let total = 0;
      for (let j = lo; j < hi; j++) {
        const v = Math.max(0, 1 - Math.abs((j + 0.5 - center) / support));
        w.push(v);
        total += v;
      }
      result.push({ lo, w: w.map((v) => v / total) });
    }
    return result;
  }

  // Thu nhỏ RGBA (sw × sh) về RGB (dw × dh): ngang trước rồi dọc, làm tròn về 0–255 sau mỗi lượt như PIL
  function pilBilinear(src, sw, sh, dw, dh) {
    const cx = resizeCoeffs(sw, dw);
    const cy = resizeCoeffs(sh, dh);
    const tmp = new Uint8ClampedArray(dw * sh * 3);
    for (let y = 0; y < sh; y++) {
      for (let x = 0; x < dw; x++) {
        const { lo, w } = cx[x];
        let r = 0, g = 0, b = 0;
        for (let k = 0; k < w.length; k++) {
          const p = (y * sw + lo + k) * 4;
          r += src[p] * w[k]; g += src[p + 1] * w[k]; b += src[p + 2] * w[k];
        }
        const q = (y * dw + x) * 3;
        tmp[q] = Math.round(r); tmp[q + 1] = Math.round(g); tmp[q + 2] = Math.round(b);
      }
    }
    const out = new Uint8ClampedArray(dw * dh * 3);
    for (let y = 0; y < dh; y++) {
      const { lo, w } = cy[y];
      for (let x = 0; x < dw; x++) {
        let r = 0, g = 0, b = 0;
        for (let k = 0; k < w.length; k++) {
          const p = ((lo + k) * dw + x) * 3;
          r += tmp[p] * w[k]; g += tmp[p + 1] * w[k]; b += tmp[p + 2] * w[k];
        }
        const q = (y * dw + x) * 3;
        out[q] = Math.round(r); out[q + 1] = Math.round(g); out[q + 2] = Math.round(b);
      }
    }
    return out;
  }

  function toTensor(bitmap) {
    const k = Math.min(1, 448 / Math.max(bitmap.width, bitmap.height));
    const mid = document.createElement("canvas");
    mid.width = Math.max(1, Math.round(bitmap.width * k));
    mid.height = Math.max(1, Math.round(bitmap.height * k));
    const mctx = mid.getContext("2d", { willReadFrequently: true });
    mctx.imageSmoothingQuality = "high";
    mctx.drawImage(bitmap, 0, 0, mid.width, mid.height);
    const src = mctx.getImageData(0, 0, mid.width, mid.height).data;
    const px = pilBilinear(src, mid.width, mid.height, 224, 224);
    const n = 224 * 224;
    const out = new Float32Array(3 * n);
    for (let i = 0; i < n; i++) {
      for (let ch = 0; ch < 3; ch++) out[ch * n + i] = (px[i * 3 + ch] / 255 - MEAN[ch]) / STD[ch];
    }
    return new ort.Tensor("float32", out, [1, 3, 224, 224]);
  }

  async function predictInBrowser(file) {
    if (!session) status.textContent = "Đang tải mô hình (45 MB), chỉ lần đầu…";
    const s = await loadSession();
    status.textContent = "Đang đọc ảnh…";
    const t0 = performance.now();
    let bitmap;
    try {
      bitmap = await createImageBitmap(file);
    } catch {
      throw new Error("Không đọc được file này. Hãy chọn ảnh JPG, PNG hoặc WebP.");
    }
    const t1 = performance.now();
    const input = toTensor(bitmap);
    bitmap.close();
    const t2 = performance.now();
    const output = await s.run({ [s.inputNames[0]]: input });
    const logits = Array.from(output[s.outputNames[0]].data);
    const t3 = performance.now();
    const max = Math.max(...logits);
    const exps = logits.map((v) => Math.exp(v - max));
    const sum = exps.reduce((a, b) => a + b, 0);
    const probs = exps.map((v) => v / sum);
    const top = probs.indexOf(Math.max(...probs));
    const t4 = performance.now();
    return {
      label: local.classes[top],
      label_vi: local.labels[local.classes[top]],
      confidence: probs[top],
      probs: local.classes.map((c, i) => ({ label: c, label_vi: local.labels[c], p: probs[i] })),
      timings_ms: { upload: t1 - t0, preprocess: t2 - t1, inference: t3 - t2, softmax: t4 - t3 },
    };
  }

  // Bản tĩnh: tải trước mô hình khi người xem cuộn tới bảng thử
  if (local) {
    new IntersectionObserver((entries, obs) => {
      if (!entries[0].isIntersecting) return;
      obs.disconnect();
      loadSession().catch(() => {});
    }, { rootMargin: "400px 0px" }).observe($("#thu"));
  }

  let busy = false;
  async function classify(file, name, alt) {
    if (busy) return;
    if (!file.type.startsWith("image/")) {
      status.textContent = "File này không phải ảnh. Hãy chọn JPG, PNG hoặc WebP.";
      status.classList.add("is-error");
      return;
    }
    busy = true;
    status.classList.remove("is-error");
    status.textContent = "Đang đọc ảnh…";
    view.classList.add("is-loading");

    demoCam.hidden = true;
    const url = URL.createObjectURL(file);
    preview.src = url;
    preview.alt = alt || `Ảnh đang được nhận diện: ${name}`;
    shutter();

    try {
      const data = local ? await predictInBrowser(file) : await predictOnServer(file, name);
      showResult(data);
      addMine(data);
      setStages(data.timings_ms);
      const total = Object.values(data.timings_ms).reduce((a, b) => a + b, 0);
      status.textContent = `${name}: đọc xong sau ${Math.round(total)} mili giây.`;
      if (data.cam) status.textContent += ` Grad-CAM mất ${ms(data.timings_ms.gradcam).toLowerCase()}.`;
    } catch (err) {
      status.textContent = err.message || "Có lỗi, hãy thử lại.";
      status.classList.add("is-error");
    } finally {
      view.classList.remove("is-loading");
      busy = false;
    }
  }

  $$("[data-pick]").forEach((btn) => btn.addEventListener("click", () => document.getElementById(btn.dataset.pick).click()));

  $$("[data-file]").forEach((input) => {
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (!file) return;
      if (input.id === "file-hero") $("#thu").scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
      $$(".sample").forEach((b) => b.classList.remove("is-active"));
      classify(file, file.name);
      input.value = "";
    });
  });

  ["dragenter", "dragover"].forEach((ev) => view.addEventListener(ev, (e) => { e.preventDefault(); view.classList.add("is-over"); }));
  ["dragleave", "drop"].forEach((ev) => view.addEventListener(ev, (e) => { e.preventDefault(); view.classList.remove("is-over"); }));
  view.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) classify(file, file.name);
  });

  $$(".sample").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = btn.dataset.sample;
      $$(".sample").forEach((b) => b.classList.toggle("is-active", b === btn));
      const blob = await (await fetch(`/assets/${name}`)).blob();
      classify(new File([blob], name, { type: blob.type || "image/jpeg" }), btn.textContent.trim(), `Ảnh đang được nhận diện: ${btn.textContent.trim()}`);
    });
  });

  // Kết quả ban đầu và thời gian trung bình của các chặng, lấy từ lần đọc ảnh khi máy chủ khởi động
  (local ? Promise.resolve(local.gallery) : fetch("/api/gallery").then((r) => r.json())).then((list) => {
    const shown = preview.getAttribute("src").split("/").pop();
    const first = list.find((r) => r.file === shown);
    if (first) showResult(first);
    const avg = (k) => list.reduce((s, r) => s + r.timings_ms[k], 0) / list.length;
    setStages({ preprocess: avg("preprocess"), inference: avg("inference"), softmax: avg("softmax") });
  }).catch(() => {});

  /* ---------- Đồng hồ Hà Nội ---------- */
  const clock = $("[data-clock]");
  const fmt = new Intl.DateTimeFormat("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit", weekday: "long" });
  const tick = () => { clock.textContent = fmt.format(new Date()); };
  tick();
  setInterval(tick, 30000);
})();
