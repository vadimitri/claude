// default: 0.56 0.80 0.38 14
// default-wide: 1.20 0.40 0.38 14
// S36 Schmelze (lab_spark.c_schmelze): Stern sackt ab und laeuft aus, Tropfen ziehen nach unten, jeder vierte
// bis zum Seitenrand in eine Lache. Die Spaltensuche ("letzte Sternzeile darueber") laeuft als Marsch nach oben.
float S36_d(vec2 p) {                                    // abgesackter, unten breit gelaufener Stern
  float R = uStar.z;
  float s = clamp((p.y - (uStar.y - R)) / (2.0 * R), 0.0, 1.0);
  return sd(vec2((p.x - uStar.x) / (1.0 + 0.28 * s * s), p.y - uStar.y - 0.32 * R * s * s), uStar.w) / R;
}
// Abstand von p nach oben bis zur naechsten Sternzelle derselben Spalte (0 = drin), -1 = keine innerhalb Lmax
float S36_up(vec2 p, float Lmax) {
  float R = uStar.z;
  if (S36_d(p) < 1.0) return 0.0;
  float yb = min(p.y, uStar.y + 1.45 * R), yt = max(p.y - Lmax, uStar.y - 1.05 * R);
  if (yb <= yt) return -1.0;
  int n = min(int(ceil((yb - yt) / (1.5 * uCell))), 160);  // Schritt <= 1.5 Zellen, sonst fehlen duenne Spitzen
  float h = (yb - yt) / float(max(n, 1));
  float y = yb;
  for (int i = 0; i <= 160; i++) {
    if (i > n) break;
    if (S36_d(vec2(p.x, y)) < 1.0) {
      float lo = y, hi = y + h;                          // lo drin, hi draussen
      for (int j = 0; j < 6; j++) { float m = 0.5 * (lo + hi); if (S36_d(vec2(p.x, m)) < 1.0) lo = m; else hi = m; }
      return p.y - lo;
    }
    y -= h;
  }
  return -1.0;
}
float S36_rnd(int k, float n) { return hash12(vec2(float(k) * 7.31 + n * 1.97, 36.0 + uSeed * 3.1)); }

// Tropfen an der Stelle q: (drip, highlight, Laufdistanz)
vec3 S36_drip(vec2 q) {
  float x0 = uStar.x, R = uStar.z;
  float L = 0.012 + 0.025 * clamp(fbm(vec2(q.x, 0.0), 0.05 * R, 361.0) + 0.3, 0.0, 1.0);
  bool hl = false, bulb = false;
  for (int k = 0; k < 16; k++) {
    float xk = x0 + R * mix(-0.9, 0.9, S36_rnd(k, 0.0));
    float wk = R * mix(0.025, 0.07, S36_rnd(k, 1.0));
    float lk = (k % 4 == 0) ? 9.0 : R * mix(0.15, 1.3, S36_rnd(k, 2.0));
    float u = (q.x - xk) / wk;
    L = max(L, lk * pow(clamp(1.0 - u * u, 0.0, 1.0), 0.25));
    hl = hl || (u > -0.75 && u < -0.35);
    float br = 1.25 * wk;
    if (lk < 5.0 && abs(q.x - xk) < br && !bulb) {       // Tropfenkopf am Ende des kurzen Laufs
      float yb = uStar.y + 1.45 * R;
      float dd = S36_up(vec2(xk, yb), 2.6 * R);
      if (dd >= 0.0) bulb = length(q - vec2(xk, yb - dd + lk)) < br;
    }
  }
  float dist = S36_up(q, L);
  bool dr = dist >= 0.0 || bulb;
  return vec3(dr ? 1.0 : 0.0, (dr && hl) ? 1.0 : 0.0, max(dist, 0.0));
}

vec4 spark_S36(vec2 p) {
  float R = uStar.z, B = uPage.y, lp = uCell;
  float d = S36_d(p);
  bool M = d < 1.0;
  float v = bg(p) + 0.12 * exp(-max(d - 1.0, 0.0) / 0.3);
  // Lache am unteren Seitenrand unter den langen Laeufen
  float pool = 0.0;
  for (int k = 0; k < 16; k += 4) {
    float xk = uStar.x + R * mix(-0.9, 0.9, S36_rnd(k, 0.0));
    float wk = R * mix(0.025, 0.07, S36_rnd(k, 1.0));
    float e = (p.x - xk) / (4.0 * wk + 0.03);
    pool += 0.035 * exp(-e * e);
  }
  float py = B - 0.012 - pool;
  bool pl = p.y > py;
  if (pl) v = p.y < py + 1.5 * lp ? 1.0 : 0.72;
  bool dr = false;
  if (!M && p.y > uStar.y - 1.05 * R) {
    // Laeufe schlingern: Spalte versetzt, staerker je weiter vom Stern
    float d0 = S36_up(p, R);
    float dist0 = d0 < 0.0 ? R : d0;
    float wob = 0.05 * R * clamp(dist0 / R, 0.0, 1.0) * sin(p.y / (0.12 * R) + 3.0 * fbm(p, 0.3 * R, 362.0));
    vec3 D = S36_drip(vec2(p.x + wob, p.y));
    if (D.x > 0.5) {
      dr = true;
      v = D.y > 0.5 ? 1.0 : 0.92 - 0.35 * clamp(D.z / 0.8, 0.0, 1.0);
    }
  }
  if (M) v = 0.6 + 0.4 * pow(clamp(1.0 - d, 0.0, 1.0), 0.7);
  bool lit = (M || dr || pl) && v >= 0.5;
  return vec4(clamp(v, 0.0, 1.0), lit ? 1.0 : 0.0, 0.0, 0.0);
}
