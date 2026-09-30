// Editor-Zustand: Kampagne, Auswahl, Undo/Redo, Ansicht
import { clone, load, newSpec, save, type Spec } from '../spec';

class Store {
  campaign = $state<Spec[]>(load() ?? [newSpec('kickoff', { pal: 'signal', spark: 'S7', K: 'K4' })]);
  cur = $state(0);
  layer = $state<string>('star');
  zoom = $state(0.2);
  panX = $state(0);
  panY = $state(0);
  sparks = $state<string[]>([]);
  variantsOpen = $state(false);
  fitReq = $state(0);
  private undo: string[] = [];
  private redo: string[] = [];

  get spec(): Spec {
    return this.campaign[Math.min(this.cur, this.campaign.length - 1)];
  }

  /** Vor jeder Aenderung (bei Drag: einmal beim Start) aufrufen. */
  checkpoint() {
    this.undo.push(JSON.stringify([this.campaign, this.cur]));
    if (this.undo.length > 200) this.undo.shift();
    this.redo = [];
  }
  private restore(from: string[], to: string[]) {
    const s = from.pop();
    if (!s) return;
    to.push(JSON.stringify([this.campaign, this.cur]));
    const [c, i] = JSON.parse(s);
    this.campaign = c;
    this.cur = i;
  }
  doUndo() { this.restore(this.undo, this.redo); }
  doRedo() { this.restore(this.redo, this.undo); }

  /** Aenderung am aktuellen Plakat, mit Undo-Punkt. */
  edit(f: (s: Spec) => void, cp = true) {
    if (cp) this.checkpoint();
    f(this.spec);
  }
  add(s: Spec, select = true) {
    this.checkpoint();
    this.campaign.splice(this.cur + 1, 0, s);
    if (select) this.cur = this.cur + 1;
  }
  duplicate() {
    const s = clone($state.snapshot(this.spec)) as Spec;
    s.id = Math.random().toString(36).slice(2, 10);
    this.add(s);
  }
  remove(i = this.cur) {
    if (this.campaign.length <= 1) return;
    this.checkpoint();
    this.campaign.splice(i, 1);
    this.cur = Math.max(0, Math.min(this.cur, this.campaign.length - 1));
  }
  persist() { save($state.snapshot(this.campaign) as Spec[]); }
}

export const st = new Store();
