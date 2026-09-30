// S33 "matrjoschka" (styles.spark): 4 Sterne ineinander (Faktor 0.64), dazwischen Luft, die nach innen in Korn ausdithert.
vec4 spark_S33(vec2 p) {
  float d = starMain(p);
  if (d >= 1.0) return vec4(-1.0, 0.0, 0.0, 0.0);
  const float n = 4.0;
  float q = log(max(d, 1e-6)) / log(0.64);                    // 0 am Aussenrand, +1 pro Puppe
  float k = floor(q), f = q - k;
  bool shell = f < 0.42 || k >= n - 1.0;
  float val = 0.60 + 0.38 * clamp(k / (n - 1.0), 0.0, 1.0);
  if (shell) return vec4(val, 1.0, 0.0, 0.0);
  float noise = hash12(floor(p / uCell) + (uSeed + 5.0) * 131.7) - 0.5;   // Korn je Zelle wie rng.random
  float fade = exp(-(f - 0.42) / 0.16);
  return vec4(clamp(0.16 + (val - 0.16) * fade + 0.22 * noise * (1.0 - fade), 0.0, 1.0), 0.0, 0.0, 0.0);
}
