// default: 0.62A 0.30B 0.46 14
// S31e "Flare" (lab_spark.c_flare): Stern als Sonne, anamorpher Lichtbalken quer ueber die Seite, Geisterbilder (Sterne,
// Bokeh-Scheibe) auf der Achse durch die Seitenmitte. Default = kickoff.OWN_K (0.62 W, 0.30 H, 0.46).
float S31e_ink(float d, float lo) { return lo + (1.0 - lo) * pow(clamp(1.0 - d, 0.0, 1.0), 0.7); }

// f-Intervall der Strecke c + (p - c) f (f in [0, 1]) innerhalb der Titel-Bbox (+2 Zellen): nur dort kann Schrift verdecken
vec2 S31e_clip(vec2 p, vec2 c) {
  vec2 dir = p - c;
  dir = mix(dir, vec2(1e-6), lessThan(abs(dir), vec2(1e-6)));
  vec4 b = uTitleBox + vec4(-2.0, -2.0, 2.0, 2.0) * uCell;
  vec2 t1 = (b.xy - c) / dir, t2 = (b.zw - c) / dir;
  vec2 lo = min(t1, t2), hi = max(t1, t2);
  return vec2(max(max(lo.x, lo.y), 0.0), min(min(hi.x, hi.y), 1.0));
}

// lab_spark._lit_band (Plakatmodus): im Titel-/Datumsband kippt Schrift ab v >= 0.2, die Kopfzeile erst ab 0.5
float S31e_litBand(vec2 p, float v) { return (p.y > uTitleBox.y - 0.025 ? v >= 0.2 : v >= 0.5) ? 1.0 : 0.0; }

// lab_spark.shafts: mittlere Emission auf der Strecke p -> Stern (emit = 1 im Stern, aussen 0.6 exp(-(d-1)/0.25)),
// Schrift schneidet die Emission weg. Unverdeckter Teil analytisch, die Schrift wird in <= 48 Schritten abgezogen.
// Normierung: 90. Perzentil im Ring d 1..1.3 ~ 0.97.
float S31e_emit(float x) { return x < 1.0 ? 1.0 : 0.6 * exp(-(x - 1.0) / 0.25); }
float S31e_shafts(vec2 p, vec2 c, float d, float gamma) {
  float full = d <= 1.0 ? 1.0 : (1.0 + 0.15 * (1.0 - exp(-(d - 1.0) / 0.25))) / d;
  vec2 fr = S31e_clip(p, c);
  float occ = 0.0;
  if (fr.y > fr.x) {
    float df = (fr.y - fr.x) / 48.0;
    for (int i = 0; i < 48; i++) {
      float f = fr.x + (float(i) + 0.5) * df;
      occ += titleMask(c + (p - c) * f) * S31e_emit(f * d);
    }
    occ *= df;
  }
  return pow(clamp((full - occ) / 0.97, 0.0, 1.2), gamma);
}

vec4 spark_S31e(vec2 p) {
  vec2 c = uStar.xy;
  float rot = uStar.w;
  float d = starMain(p);
  float A = uPage.x;
  float dy = abs(p.y - c.y), dx = abs(p.x - c.x);
  float wing = exp(-dy / (0.012 + 0.02 * exp(-dx / 0.5))) * exp(-dx / (0.9 * A));
  float v = bg(p, 0.0, 0.04) + 0.7 * S31e_shafts(p, c, d, 1.2) + 0.75 * wing;
  if (dy < 1.01 * uCell) v = max(v, 0.6 + 0.4 * exp(-dx / (0.8 * A)));   // harter Kern des Balkens
  // Geisterbilder auf der Achse Stern -> Seitenmitte
  vec2 ax = uPage * 0.5 - c;
  float n = length(ax);
  if (n < 0.15) { ax = vec2(0.0, uPage.y * 0.5); n = uPage.y * 0.5; }  // Stern schon mittig: Achse nach unten
  vec2 u = ax / n;
  float L = length(uPage);
  const vec4 TQ = vec4(0.28, 0.42, 0.60, 0.78), SZ = vec4(0.05, 0.018, 0.11, 0.035), RO = vec4(30.0, 0.0, 30.0, 0.0),
             LV = vec4(0.42, 0.8, 0.22, 0.55);
  for (int k = 0; k < 4; k++) {
    vec2 gp = c + u * TQ[k] * L;
    float dg = star(p, gp.x, gp.y, SZ[k], rot + RO[k]);
    if (dg < 1.0) v = max(v, LV[k] * (0.75 + 0.25 * (1.0 - dg)));
  }
  float rr = length(p - (c + u * 0.5 * L));
  if (rr < 0.26) v = max(v, 0.16 + 0.06 * pow(rr / 0.26, 4.0));      // Bokeh-Scheibe, Rand etwas heller
  if (d < 1.0) v = S31e_ink(d, 0.8);
  v = clamp(v, 0.0, 1.0);
  return vec4(v, v >= 0.45 ? 1.0 : 0.0, 0.0, 0.0);                   // per_pixel
}
