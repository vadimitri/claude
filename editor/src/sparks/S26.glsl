// default: 0.60A 0.40B 0.80 0
// S26 "Kippschrift" (lab_spark.c_xortitel): Glutstern riesig hinter dem Titel; wo die Schrift ihn kreuzt, kippt sie ins
// Negativ (lit). Default = kickoff.OWN_K (0.60 W, 0.40 H, 0.80).
// Python ohne OWN_K: (bb0 + 0.58 w, Titelmitte + 0.25 h, min(0.54 w, 0.55 B, 0.46 A)), rot 0.

bool S26_in(vec2 q) { return starMain(q) < 1.0; }
bool S26_ero(vec2 q) {
  vec2 e = vec2(uCell, 0.0);
  return S26_in(q) && S26_in(q + e) && S26_in(q - e) && S26_in(q + e.yx) && S26_in(q - e.yx);
}

vec4 spark_S26(vec2 p) {
  float d = starMain(p);
  // clean(d < 1, 1): Oeffnung mit Kreuz (erode + dilate), keine 1-Zellen-Splitter an den Spitzen
  vec2 e = vec2(uCell, 0.0);
  bool s = d < 1.0 && (S26_ero(p) || S26_ero(p + e) || S26_ero(p - e) || S26_ero(p + e.yx) || S26_ero(p - e.yx));
  float v = s ? 0.5 + 0.5 * pow(clamp(1.0 - d, 0.0, 1.0), 0.7)
              : bg(p) + 0.10 * exp(-max(d - 1.0, 0.0) / 0.18);
  return vec4(clamp(v, 0.0, 1.0), s ? 1.0 : 0.0, 0.0, 0.0);
}
