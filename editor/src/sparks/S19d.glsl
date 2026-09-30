// default: 0.50 0.84 0.52 0
// default-wide: 1.28 0.52 0.52 0
// S19d "Nest-Rosette" (lab_spark.c_kaleido_nest): XOR-Nest aus der Mitte geschoben und sechsfach gespiegelt.
vec2 S19d_fold(vec2 q, float n) {                              // Dieder-Faltung D_n: Keil [0, pi/n], gespiegelt
  float w = 6.28318530718 / n;
  float th = mod(atan(q.y, q.x), w);
  th = min(th, w - th);
  return length(q) * vec2(cos(th), sin(th));
}
vec4 spark_S19d(vec2 p) {
  float R = uStar.z, a = radians(uStar.w), c = cos(a), s = sin(a);
  vec2 dd = p - uStar.xy;
  vec2 q = vec2(dd.x * c + dd.y * s, -dd.x * s + dd.y * c) / R;
  float D0 = sd(q, 0.0);
  vec2 fq = S19d_fold(q, 6.0);
  bool par = false;
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    if (sd(fq - vec2(0.42, 0.0), 30.0 + 30.0 * fk) < 0.5 * pow(0.74, fk)) par = !par;
  }
  if (sd(q, 30.0) < 0.30) par = !par;
  if (sd(q, 0.0) < 0.16) par = !par;
  par = (par && D0 < 1.0) || (D0 >= 0.8 && D0 < 1.0);         // harter Rand: Spitzen spitz
  if (par) return vec4(0.5 + 0.5 * pow(clamp(1.0 - D0 * 0.9, 0.0, 1.0), 0.7), 1.0, 0.0, 0.0);
  return vec4(bg(p) + 0.12 * exp(-max(D0 - 1.0, 0.0) / 0.35), 0.0, 0.0, 0.0);
}
