/* generated from content/paper.html */
const IC_LARGE = [["downside_dev","volatility",-0.0377,-1.55],["rev_overnight","reversal",0.0287,1.46],["lowvol_250","volatility",-0.0389,-1.43],["vol_price_conf","liquidity",-0.0193,-1.36],["lowvol_60","volatility",-0.0352,-1.36],["max_daily_ret","shape",-0.0276,-1.31],["vol_of_vol","volatility",-0.0225,-1.26],["shallow_dd","shape",-0.0245,-0.95],["negative_skew","shape",0.0123,0.94],["small_dollar_vol","liquidity",-0.0158,-0.83],["rev_21d","reversal",0.0159,0.77],["mom_consistency","momentum",0.0142,0.72],["volume_shock","liquidity",0.0091,0.72],["vol_trend","volatility",-0.0101,-0.69],["near_52w_high","momentum",-0.0168,-0.68],["mom_1m","momentum",-0.0129,-0.62],["close_location","technical",0.0095,0.56],["mom_accel","momentum",-0.013,-0.54],["mom_3_1","momentum",-0.0103,-0.49],["mom_12_1","momentum",0.0108,0.45],["trend_quality","shape",-0.0095,-0.43],["up_day_ratio","shape",-0.0073,-0.4],["bollinger","technical",0.0061,0.32],["illiquidity","liquidity",-0.0049,-0.28],["rev_1d","reversal",0.0049,0.26],["ma_cross_50_200","technical",0.0049,0.21],["intraday_drift","reversal",0.0031,0.17],["rsi_14","technical",0.0031,0.16],["dist_200ma","technical",0.0037,0.15],["mom_6_1","momentum",-0.0008,-0.03],["rev_5d","reversal",-0.0006,-0.03]];
const IC_SMALL = [["illiquidity","liquidity",0.0289,2.06],["close_location","technical",-0.0241,-1.7],["near_52w_high","momentum",-0.03,-1.49],["shallow_dd","shape",-0.0321,-1.45],["rev_overnight","reversal",0.0244,1.45],["small_dollar_vol","liquidity",0.0197,1.26],["mom_6_1","momentum",-0.0218,-1.25],["vol_trend","volatility",0.0171,1.22],["trend_quality","shape",-0.0194,-1.19],["lowvol_250","volatility",-0.0264,-1.14],["downside_dev","volatility",-0.0248,-1.11],["negative_skew","shape",0.0132,1.08],["bollinger","technical",0.0153,0.98],["vol_of_vol","volatility",-0.0145,-0.91],["mom_1m","momentum",-0.0162,-0.9],["lowvol_60","volatility",-0.02,-0.88],["mom_accel","momentum",0.0165,0.86],["mom_12_1","momentum",-0.0163,-0.81],["rev_21d","reversal",0.0145,0.81],["rsi_14","technical",0.0123,0.79],["mom_3_1","momentum",-0.0129,-0.73],["dist_200ma","technical",-0.0135,-0.71],["up_day_ratio","shape",-0.0093,-0.64],["rev_5d","reversal",0.0108,0.59],["ma_cross_50_200","technical",-0.0108,-0.58],["volume_shock","liquidity",0.0067,0.58],["vol_price_conf","liquidity",-0.0052,-0.44],["mom_consistency","momentum",-0.0064,-0.38],["rev_1d","reversal",0.0065,0.35],["max_daily_ret","shape",-0.0019,-0.1],["intraday_drift","reversal",-0.0015,-0.09]];
const EIG_LARGE = [10.698,5.2117,4.3905,2.105,1.3996,1.2333,1.171,0.9199,0.7777,0.5632,0.4069,0.3476,0.3153,0.2555,0.2447,0.1916,0.1481,0.1128,0.0885,0.0745,0.0676,0.0635,0.0531,0.0415,0.0358,0.021,0.0204,0.0149,0.0107,0.0097,0.0065];
const EIG_SMALL = [9.852,5.1659,4.3817,2.0425,1.534,1.1709,1.0619,1.0124,0.8757,0.662,0.5229,0.4659,0.424,0.3349,0.2653,0.2447,0.1978,0.1474,0.1217,0.0985,0.0918,0.0746,0.0659,0.0455,0.04,0.028,0.0224,0.0162,0.0132,0.0108,0.0094];

const NS = "http://www.w3.org/2000/svg";
function el(tag, attrs, text){
  const n = document.createElementNS(NS, tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (text !== undefined) n.textContent = text;
  return n;
}
function svg(w, h){
  const s = el("svg", {viewBox:`0 0 ${w} ${h}`, width:w, height:h,
                       preserveAspectRatio:"xMidYMin meet", role:"img"});
  return s;
}

/* ---- Figure 1: dumbbell of t-statistics ---- */
(function(){
  const host = document.getElementById("fig-t");
  if (!host) return;
  const small = new Map(IC_SMALL.map(r => [r[0], r[3]]));
  const rows = IC_LARGE.map(r => ({name:r[0], fam:r[1], L:r[3], S:small.get(r[0])}));

  const W = 720, rowH = 19, padT = 62, padB = 34, padL = 132, padR = 22;
  const H = padT + rows.length * rowH + padB;
  const x0 = padL, x1 = W - padR;
  const dom = 2.6;
  const X = v => x0 + (v + dom) / (2 * dom) * (x1 - x0);
  const s = svg(W, H);

  for (const t of [-2,-1,0,1,2]){
    s.appendChild(el("line",{x1:X(t),x2:X(t),y1:padT-12,y2:H-padB+4,
      class: t===0 ? "zero" : (Math.abs(t)===2 ? "thresh" : "grid")}));
    s.appendChild(el("text",{x:X(t),y:padT-18,class:"ax","text-anchor":"middle"}, t.toFixed(0)));
  }
  s.appendChild(el("text",{x:X(0),y:H-8,class:"axlab","text-anchor":"middle"},
    "rank IC t-statistic  (overlap-deflated)"));

  rows.forEach((r,i) => {
    const y = padT + i*rowH + rowH/2;
    s.appendChild(el("text",{x:padL-12,y:y+3.5,class:"ax","text-anchor":"end"}, r.name));
    if (r.S !== undefined)
      s.appendChild(el("line",{x1:X(r.L),x2:X(r.S),y1:y,y2:y,class:"link"}));
    if (r.S !== undefined)
      s.appendChild(el("circle",{cx:X(r.S),cy:y,r:3.6,fill:"var(--paper)",
        stroke:"var(--accent)","stroke-width":1.4}));
    s.appendChild(el("circle",{cx:X(r.L),cy:y,r:3.6,fill:"var(--accent)"}));
  });

  const lg = el("g",{});
  lg.appendChild(el("circle",{cx:padL+6,cy:padT-42,r:3.6,fill:"var(--accent)"}));
  lg.appendChild(el("text",{x:padL+16,y:padT-38.5,class:"ax"},"large cap (112)"));
  lg.appendChild(el("circle",{cx:padL+122,cy:padT-42,r:3.6,fill:"var(--paper)",
    stroke:"var(--accent)","stroke-width":1.4}));
  lg.appendChild(el("text",{x:padL+132,y:padT-38.5,class:"ax"},"small cap (110)"));
  s.appendChild(lg);
  host.appendChild(s);
})();

/* ---- Figure 2: eigenvalue spectrum ---- */
(function(){
  const host = document.getElementById("fig-eig");
  if (!host || !EIG_LARGE) return;
  const L = EIG_LARGE, S = EIG_SMALL;
  const n = L.length;
  const W = 720, padT = 34, padB = 46, padL = 46, padR = 18, H = 300;
  const x0 = padL, x1 = W - padR, y0 = H - padB, y1 = padT;
  const maxY = Math.ceil(Math.max(...L, ...(S||[0])));
  const Y = v => y0 - (v / maxY) * (y0 - y1);
  const bw = (x1 - x0) / n;
  const s = svg(W, H);

  for (let t = 0; t <= maxY; t += 2){
    s.appendChild(el("line",{x1:x0,x2:x1,y1:Y(t),y2:Y(t),class:"grid"}));
    s.appendChild(el("text",{x:x0-9,y:Y(t)+3.5,class:"ax","text-anchor":"end"}, t.toFixed(0)));
  }
  s.appendChild(el("line",{x1:x0,x2:x1,y1:Y(1),y2:Y(1),class:"thresh"}));
  s.appendChild(el("text",{x:x1,y:Y(1)-7,class:"ax","text-anchor":"end"},
    "λ = 1  (every signal independent)"));

  L.forEach((v,i) => {
    s.appendChild(el("rect",{x:x0+i*bw+1.5, y:Y(v), width:Math.max(1,bw-3),
      height:Math.max(0.5, y0-Y(v)), fill:"var(--accent)"}));
  });
  if (S) S.forEach((v,i) => {
    s.appendChild(el("line",{x1:x0+i*bw+1.5, x2:x0+i*bw+bw-1.5, y1:Y(v), y2:Y(v),
      stroke:"var(--oxide)", "stroke-width":1.6}));
  });

  [1,10,20,31].forEach(k => {
    s.appendChild(el("text",{x:x0+(k-0.5)*bw, y:y0+15, class:"ax","text-anchor":"middle"}, k));
  });
  s.appendChild(el("text",{x:(x0+x1)/2, y:H-8, class:"axlab","text-anchor":"middle"},
    "eigenvalue rank  ·  bars = large cap, rules = small cap"));
  s.appendChild(el("text",{x:12, y:padT-14, class:"axlab"}, "λ"));
  host.appendChild(s);
})();

/* ---- Figure 3: the breadth gap ---- */
(function(){
  const host = document.getElementById("fig-gap");
  if (!host) return;
  const data = [
    {lab:"Available: 31 signals, monthly", v:67, tone:"var(--accent)"},
    {lab:"Required for IR 0.5", v:1276, tone:"var(--oxide)"},
    {lab:"Required for IR 1.0", v:5102, tone:"var(--oxide)"}
  ];
  const W = 720, padL = 240, padR = 70, padT = 30, padB = 40, rowH = 46;
  const H = padT + data.length*rowH + padB;
  const x0 = padL, x1 = W - padR;
  const lo = Math.log10(10), hi = Math.log10(10000);
  const X = v => x0 + (Math.log10(v) - lo) / (hi - lo) * (x1 - x0);
  const s = svg(W, H);

  [10,100,1000,10000].forEach(t => {
    s.appendChild(el("line",{x1:X(t),x2:X(t),y1:padT-8,y2:H-padB+2,class:"grid"}));
    s.appendChild(el("text",{x:X(t),y:H-padB+17,class:"ax","text-anchor":"middle"},
      t.toLocaleString()));
  });
  s.appendChild(el("text",{x:(x0+x1)/2,y:H-8,class:"axlab","text-anchor":"middle"},
    "independent bets per year  (log scale)"));

  data.forEach((d,i) => {
    const y = padT + i*rowH + 10;
    s.appendChild(el("text",{x:padL-16,y:y+13,class:"ax","text-anchor":"end"}, d.lab));
    s.appendChild(el("rect",{x:x0,y:y,width:Math.max(2,X(d.v)-x0),height:20,fill:d.tone}));
    s.appendChild(el("text",{x:X(d.v)+9,y:y+14.5,class:"ax",fill:"var(--ink)"},
      d.v.toLocaleString()));
  });
  host.appendChild(s);
})();
