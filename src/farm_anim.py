"""Clips of the hoofed farm animals: deer_anim's clips for a farm_body.Hoofed species (2026-10-20).

The deer's numbers are in its metres. Here they are scaled to the animal: trunk motions by KB (the body), foot and
stride distances by KL (the legs), and the cadence by sqrt(KL) (shorter legs, quicker steps). Neck shapes for grazing
and lying come from the species (sp.GRAZE, sp.LIE_NECK), because a goat's neck is not a stag's.

Clips (30 fps, the animal faces -Y; Unity +Z):
  Idle    loop    breathing, a weight shift, ear flicks, a tail flick, a slow look round, a hind foot cocked
  Graze   loop    head down at the grass, chewing, ears turning, a slow step forward (root motion)
  Alert           head up high, ears forward, tail up, a forefoot stamp; holds the end
  Call            head up and forward, the mouth opens twice (bleat, moo, neigh, grunt: the game's sound)
  Walk    loop    four-beat lateral walk, the head nodding
  Trot    loop    two-beat diagonal trot
  Run     loop    the gallop
  Attack          (sp.ATTACK: the goat's butt) head down, a lunge (event 'Bite' at the hit)
  Hit             a flinch sideways
  Death           the legs fold, it falls onto its left side, the head last (event 'Dead'); holds
  Sleep   loop    lying on its belly, legs folded under, the head low
  Wake            rises hind end first, ends in the Idle stance
"""
import math
from mathutils import Vector
import beast_anim as BA
from beast_anim import LegPose, K, ease, WALK, TROT, GALLOP

FPS = 30
FWD = Vector((0, -1, 0))


def _bump(f, c, width):
    return max(0.0, 1 - abs(f - c) / width)


def _flick(f, c, w=3.0, amp=-35.0):
    return amp * _bump(f, c, w)


class FarmAnim:
    FPS = FPS

    def __init__(self, sp):
        self.sp = sp
        self.SPEC = BA.Species(sp.rest_bones, tuple(sp.W(sp.BODY_C)), sp.NAME, sp.NAME + "Rig", neck_n=3,
                               tail_n=len(sp.TAIL) - 1, tongue=False)
        self.hb, self.hl = sp.KB, sp.KL                 # body and leg scales
        self.ts = math.sqrt(sp.KL) * sp.CADENCE         # time scale: < 1 is quicker
        self.EVENTS = {"Death": [("Dead", 1.9 * self.ts)]}
        self.CLIPS = {"Idle": self._clip_idle, "Graze": self._clip_graze, "Alert": self._clip_alert,
                      "Call": self._clip_call, "Walk": self._clip_walk, "Trot": self._clip_trot,
                      "Run": self._clip_run}
        if sp.ATTACK:
            self.CLIPS["Attack"] = self._clip_attack
            self.EVENTS["Attack"] = [("Bite", 15.0 / FPS * self.ts)]
        self.CLIPS.update({"Hit": self._clip_hit, "Death": self._clip_death, "Sleep": self._clip_sleep,
                           "Wake": self._clip_wake})
        self.MOVING = {"Graze", "Walk", "Trot", "Run"}
        self.SHEET_FRAMES = {n: self._sheet(n) for n in self.CLIPS}

    # ------------------------------------------------------------------ helpers
    def N(self, n):
        return max(8, int(round(n * self.ts)))

    def F(self, n, f):
        """A deer frame number mapped into this clip's length."""
        return f * self.N(n) / n

    def pose(self):
        return BA.Pose(self.SPEC)

    def neutral(self, key):
        return BA.neutral(self.SPEC, key)

    def action_name(self, clip):
        return self.SPEC.action_name(clip)

    def _ears(self, p, fwd, splay=0.0, flickL=0.0, flickR=0.0, turnL=0.0, turnR=0.0):
        e = self.sp.EAR_SWING
        p.ears = {1: [(fwd + flickL + turnL) * e, splay * e], -1: [(fwd + flickR + turnR) * e, splay * e]}

    def _tail(self, p, lift, swing=0.0, phase=0.0):
        k = self.sp.TAIL_SWING
        for i in range(self.SPEC.tail_n):
            p.tail[i] = [(lift if i == 0 else lift * 0.5) * k, swing * k * math.sin(phase - 0.8 * i), 0.0]

    def _neck(self, p, pitches, yaws=(0, 0, 0)):
        for i in range(3):
            p.neck[i] = [pitches[i], yaws[i], 0.0]

    def _sheet(self, name):
        N = self.N({"Idle": 120, "Graze": 150, "Alert": 45, "Call": 45, "Walk": 36, "Trot": 20, "Run": 14,
                    "Attack": 36, "Hit": 15, "Death": 66, "Sleep": 120, "Wake": 60}[name])
        k = {"Sleep": 2, "Hit": 4, "Run": 5}.get(name, 6)
        return tuple(sorted({int(round(N * i / k)) for i in range(k + (0 if name in ("Sleep",) else 1))}))

    def K(self, n, keys, f, loop=None):
        """K() with deer frame numbers, rescaled into this clip's length."""
        s = self.N(n) / n
        return K([(a * s, b) for a, b in keys], f, loop)

    # ------------------------------------------------------------------ idle and grazing
    def _clip_idle(self):
        n0 = 120
        N = self.N(n0)
        hb, hl = self.hb, self.hl
        Kf = lambda keys, f: self.K(n0, keys, f, N)

        def fn(f):
            p = self.pose()
            a = 2 * math.pi * f / N
            b = 2 * math.pi * f / (N / 3)
            shift = Kf([(0, 0), (34, 0), (44, 1), (70, 1), (80, 0), (120, 0)], f)
            p.body = Vector(((0.010 * math.sin(a) + 0.018 * shift) * hb, 0, 0.004 * math.sin(b) * hb))
            p.roll = 0.8 * math.sin(a) + 1.5 * shift
            p.spine[2][0] = 0.6 * math.sin(b)
            look = Kf([(0, 0), (16, 0), (34, 26), (58, 26), (76, -10), (100, -10), (112, 0), (120, 0)], f)
            nod = Kf([(0, 0), (34, -3), (58, -3), (76, 2), (112, 0), (120, 0)], f)
            self._neck(p, (1.5 * math.sin(a) + nod, 0.8 * math.sin(a + 0.5), 0), (look * 0.25, look * 0.25, look * 0.2))
            p.head = [1.5 * math.sin(b + 1.0) - nod, look * 0.3, 0]
            F = lambda c: self.F(n0, c)
            self._ears(p, 6, 0, flickL=_flick(f, F(22)), flickR=_flick(f, F(88)) + _flick(f, F(95)),
                       turnL=-14 * Kf([(0, 0), (60, 0), (66, 1), (80, 1), (86, 0), (120, 0)], f))
            flick = math.sin(2 * math.pi * f / 5) * Kf([(0, 0), (96, 0), (100, 1), (108, 1), (112, 0), (120, 0)], f)
            self._tail(p, 4 + 8 * abs(flick), 20 * flick)
            rest = Kf([(0, 0), (40, 0), (46, 1), (70, 1), (76, 0), (120, 0)], f)
            H0 = self.neutral(('H', -1))
            lp = LegPose(target=H0 + Vector((0, -0.04 * rest * hl, 0.03 * rest * hl)))
            lp.flex = 14 * rest
            lp.toe = 20 * rest
            p.legs[('H', -1)] = lp
            return p
        return N, fn, True

    def _clip_graze(self):
        n0 = 150
        N = self.N(n0)
        sp, hb, hl = self.sp, self.hb, self.hl
        step = 0.16 * hl
        Kf = lambda keys, f: self.K(n0, keys, f, N)
        pitches, head, drop, tilt = sp.GRAZE

        def fn(f):
            p = self.pose()
            a = 2 * math.pi * f / N
            b = 2 * math.pi * f / (N / 3)
            F = lambda c: self.F(n0, c)
            p.root = FWD * (step * ease((f - F(70)) / F(44)))
            p.body = Vector((0.006 * math.sin(a) * hb, 0.03 * hb, (-drop + 0.003 * math.sin(b)) * hb))
            p.pitch = sp.GRAZE_PITCH
            sweep = 6 * math.sin(a) + 3 * math.sin(2 * a + 1)
            bite = Kf([(0, 0), (20, 0), (24, 1), (30, 0), (90, 0), (94, 1), (100, 0), (150, 0)], f)
            self._neck(p, (pitches[0] + 1.5 * math.sin(b) - 2 * bite, pitches[1] - 2 * bite, pitches[2]),
                       (sweep * 0.3, sweep * 0.3, sweep * 0.2))
            p.head = [head + 2 * math.sin(b + 1) + 3 * bite, sweep * 0.3, tilt + 3 * math.sin(a)]
            chew = 1 - bite
            p.jaw = 3 + 4 * chew * (0.5 + 0.5 * math.sin(2 * math.pi * f / 9)) + 6 * bite
            self._ears(p, 2, 6, flickL=_flick(f, F(48)), flickR=_flick(f, F(128)),
                       turnL=-20 * Kf([(0, 0), (56, 0), (62, 1), (84, 1), (90, 0), (150, 0)], f),
                       turnR=18 * Kf([(0, 0), (104, 0), (110, 1), (124, 1), (130, 0), (150, 0)], f))
            self._tail(p, 2, 6, 2 * a)
            steps = {('H', 1): 68, ('F', 1): 78, ('H', -1): 92, ('F', -1): 102}
            for key, c in steps.items():
                q = min(max((f - F(c)) / F(14), 0.0), 1.0)
                F0 = self.neutral(key)
                tgt = F0 + FWD * (step * ease(q))
                tgt.z += 0.07 * hl * math.sin(math.pi * q)
                lp = LegPose(target=tgt)
                sw = math.sin(math.pi * q)
                lp.flex = (-60 if key[0] == 'F' else 30) * sw
                lp.toe = -12 * sw
                if key[0] == 'F':
                    lp.scap = 6 * (ease(q) - 0.5) * (0 < q < 1)
                p.legs[key] = lp
            return p
        return N, fn, True

    def _clip_alert(self):
        n0 = 45
        N = self.N(n0)
        sp, hb, hl = self.sp, self.hb, self.hl
        Kf = lambda keys, f: self.K(n0, keys, f)

        def fn(f):
            p = self.pose()
            up = Kf([(0, 0), (5, 1.05), (9, 1.0), (45, 1.0)], f)
            tense = Kf([(0, 0), (6, 1), (45, 1)], f)
            p.body = Vector((0, 0.025 * tense * hb, -0.015 * tense * hb))
            p.pitch = 2 * tense
            pitches, head = sp.UP_HIGH
            look = Kf([(0, 0), (8, 0), (14, 8), (45, 8)], f)
            self._neck(p, [x * up for x in pitches], (look * 0.3, look * 0.3, look * 0.2))
            p.head = [head * up, look * 0.3, 0]
            self._ears(p, 26 * up, -6 * up)
            self._tail(p, 30 * tense)
            lift = Kf([(0, 0), (14, 0), (19, 1), (22, 1), (24.5, 0), (45, 0)], f)
            F0 = self.neutral(('F', 1))
            lp = LegPose(target=F0 + Vector((0, -0.02 * lift * hl, 0.13 * lift * hl)))
            lp.flex = -55 * lift
            lp.toe = -15 * lift
            p.legs[('F', 1)] = lp
            return p
        return N, fn, False

    def _clip_call(self):
        """Head up and forward, the mouth opens twice, then back to the stance."""
        n0 = 45
        N = self.N(n0)
        sp, hb = self.sp, self.hb
        Kf = lambda keys, f: self.K(n0, keys, f)

        def fn(f):
            p = self.pose()
            up = Kf([(0, 0), (8, 1), (36, 1), (45, 0)], f)
            p.body = Vector((0, -0.01 * up * hb, 0.005 * up * hb))
            self._neck(p, (6 * up, 4 * up, 2 * up))
            p.head = [sp.CALL_HEAD * up, 0, 0]
            p.jaw = sp.CALL_JAW * Kf([(0, 0), (8, 0), (12, 1), (18, 0.6), (22, 1), (32, 0.9), (38, 0), (45, 0)], f)
            p.spine[2][0] = 2 * up
            self._ears(p, -10 * up, 8 * up)
            self._tail(p, 10 * up, 6 * up, 2 * math.pi * f / 10)
            return p
        return N, fn, False

    # ------------------------------------------------------------------ locomotion
    def _clip_walk(self):
        n0 = 36
        N = self.N(n0)
        hb, hl = self.hb, self.hl

        def fn(f):
            p = self.pose()
            BA.gait(self.SPEC, p, f, N, 1.30 * hl, 0.62, 0.10 * hl, WALK, front_fold=80, hind_flex=40, scap=14)
            a = 2 * math.pi * f / N
            p.body = Vector((0.010 * math.sin(a) * hb, 0, (-0.012 - 0.010 * math.cos(2 * a)) * hb))
            p.roll = 1.5 * math.sin(a)
            p.yaw = 1.5 * math.sin(a + 0.8)
            p.pitch = 0.6 * math.sin(2 * a)
            for i in range(3):
                p.spine[i][1] = -1.2 * math.sin(a + 0.8)
            nod = 3.0 * math.sin(2 * a + 1.0)
            self._neck(p, (-2 + nod, -1 + 0.5 * nod, 0), (-1.5 * math.sin(a), 0, 0))
            p.head = [1 - 1.2 * nod, -1.5 * math.sin(a), 0]
            self._ears(p, 4, 2 + 3 * math.sin(2 * a))
            self._tail(p, 2, 5, a)
            return p
        return N, fn, True

    def _clip_trot(self):
        n0 = 20
        N = self.N(n0)
        hb, hl = self.hb, self.hl

        def fn(f):
            p = self.pose()
            BA.gait(self.SPEC, p, f, N, 1.95 * hl, 0.40, 0.16 * hl, TROT, front_fold=105, hind_flex=50, scap=20)
            a = 2 * math.pi * f / N
            p.body = Vector((0, 0, (-0.018 - 0.016 * math.cos(2 * a)) * hb))
            p.roll = 1.0 * math.sin(a)
            p.pitch = -1 + 0.8 * math.sin(2 * a)
            bob = 1.6 * math.sin(2 * a + 1.2)
            self._neck(p, (2 + bob, 1, 0))
            p.head = [-1 - bob, 0, 0]
            self._ears(p, -4, 0)
            self._tail(p, 12, 4, a)
            return p
        return N, fn, True

    def _clip_run(self):
        n0 = 14
        N = self.N(n0)
        sp, hb, hl = self.sp, self.hb, self.hl
        stride, back = sp.RUN

        def fn(f):
            p = self.pose()
            BA.gait(self.SPEC, p, f, N, stride * hl, 0.28, 0.24 * hl, GALLOP, front_fold=120, hind_flex=62, scap=32)
            a = 2 * math.pi * f / N
            flexb = math.cos(a - 0.5) * back
            p.body = Vector((0, 0, (-0.02 + 0.06 * math.sin(a - 1.2)) * hb))
            p.pitch = -1 + 4 * math.sin(a - 0.3)
            p.spine[0][0] = 8 * flexb
            p.spine[2][0] = -7 * flexb
            p.hips = [-10 * flexb, 0, 0]
            reach = 3 * math.sin(a - 0.3)
            pitches, head = sp.RUN_NECK
            self._neck(p, (pitches[0] - reach, pitches[1], pitches[2]))
            p.head = [head + reach, 0, 0]
            p.jaw = 4
            self._ears(p, -28, -4)
            self._tail(p, 45, 4, a)
            return p
        return N, fn, True

    # ------------------------------------------------------------------ the attack and hits
    def _clip_attack(self):
        """The butt: rears back a little, head down and horns forward, lunges in (event at the hit), backs off."""
        n0 = 36
        N = self.N(n0)
        hb, hl = self.hb, self.hl
        Kf = lambda keys, f: self.K(n0, keys, f)

        def fn(f):
            p = self.pose()
            lunge = Kf([(0, 0), (9, -0.08), (13, 0.22), (16, 0.26), (24, 0.12), (36, 0)], f) * hl
            p.body = Vector((0, -lunge, Kf([(0, 0), (9, -0.06), (13, -0.02), (16, 0.02), (36, 0)], f) * hb))
            p.pitch = Kf([(0, 0), (9, -5), (13, 2), (16, 4), (24, 1), (36, 0)], f)
            p.hips = [Kf([(0, 0), (9, 4), (14, -6), (36, 0)], f), 0, 0]
            dip = Kf([(0, 0), (9, 1), (13, 1.1), (15, 0.9), (19, 0.2), (26, -0.05), (36, 0)], f)
            self._neck(p, (-18 * dip, -16 * dip, -10 * dip))
            p.head = [-30 * dip, 0, 0]
            self._ears(p, Kf([(0, 0), (6, -30), (28, -30), (36, 0)], f), -8)
            self._tail(p, Kf([(0, 0), (8, 20), (28, 20), (36, 0)], f))
            step = Kf([(0, 0), (9, 0), (14, 1), (24, 1), (32, 0), (36, 0)], f)
            lift = Kf([(0, 0), (9, 0), (11.5, 1), (14, 0), (24, 0), (28, 1), (32, 0), (36, 0)], f)
            F0 = self.neutral(('F', -1))
            lp = LegPose(target=F0 + Vector((0, -0.26 * step * hl, 0.12 * lift * hl)))
            lp.flex = -60 * lift
            lp.toe = -12 * lift
            lp.scap = 12 * step
            p.legs[('F', -1)] = lp
            for s in (1, -1):
                lp = LegPose(target=self.neutral(('H', s)))
                lp.flex = Kf([(0, 0), (9, 14), (14, -8), (36, 0)], f)
                p.legs[('H', s)] = lp
            return p
        return N, fn, False

    def _clip_hit(self):
        n0 = 15
        N = self.N(n0)
        hb = self.hb
        Kf = lambda keys, f: self.K(n0, keys, f)

        def fn(f):
            p = self.pose()
            k = Kf([(0, 0), (3, 1), (7, 0.6), (11, -0.15), (15, 0)], f)
            p.body = Vector((0.06 * k * hb, 0.04 * k * hb, -0.025 * max(k, 0) * hb))
            p.roll, p.yaw = 7 * k, -6 * k
            self._neck(p, (-6 * k, -4 * k, 0), (-8 * k, -6 * k, -4 * k))
            p.head = [6 * k, -10 * k, 10 * k]
            p.jaw = Kf([(0, 0), (3, 10), (8, 2), (15, 0)], f)
            self._ears(p, Kf([(0, 0), (2, -40), (9, -15), (15, 0)], f), 10 * max(k, 0))
            self._tail(p, Kf([(0, 0), (3, 25), (15, 0)], f))
            return p
        return N, fn, False

    def _clip_death(self):
        n0 = 66
        N = self.N(n0)
        sp, hb, hl = self.sp, self.hb, self.hl
        Kf = lambda keys, f: self.K(n0, keys, f)
        c = sp.W(sp.BODY_C)[2]
        down = c - sp.SIDE_REST                          # the trunk's centre drops this far, lying on its side
        sx = sp.KX

        def fn(f):
            p = self.pose()
            p.roll = Kf([(0, 0), (8, -4), (18, 8), (28, 40), (36, 78), (42, 86), (48, 84), (66, 85)], f)
            p.body = Vector((Kf([(0, 0), (8, -0.03), (28, 0.10), (36, 0.20), (42, 0.24), (66, 0.24)], f) * sx,
                             Kf([(0, 0), (8, -0.02), (30, 0.04), (66, 0.04)], f) * hb,
                             Kf([(0, 0), (8, -0.02 / 0.69), (18, -0.16 / 0.69), (28, -0.40 / 0.69), (36, -0.62 / 0.69),
                                 (42, -1), (48, -1 + 0.02 / 0.69), (66, -1)], f) * down))
            p.pitch = Kf([(0, 0), (8, 3), (20, -7), (34, -2), (66, -2)], f)
            jerk = Kf([(0, 0), (4, 1), (12, 0)], f)
            dn = Kf([(0, 0), (36, 0), (50, 1), (66, 1)], f)
            self._neck(p, (8 * jerk + 6 * (1 - dn) * Kf([(0, 0), (20, 1), (66, 1)], f) - 10 * dn, -6 * dn, -4 * dn),
                       (0, 6 * dn, 4 * dn))
            p.head = [-4 * jerk - 6 * dn, 8 * dn, sp.DEATH_HEAD_ROLL * dn]
            p.jaw = Kf([(0, 0), (4, 14), (20, 8), (66, 6)], f)
            self._ears(p, Kf([(0, 0), (4, -40), (66, -20)], f), 10 * dn)
            self._tail(p, Kf([(0, 0), (6, 20), (30, 0), (66, -6)], f))
            wb = Kf([(0, 0), (14, 0), (30, 1), (66, 1)], f)
            fold = Kf([(0, 0), (10, 0), (24, 1), (66, 0.7)], f)
            for kind, s in BA.LEGS:
                lp = LegPose(wb=wb)
                up_side = s < 0
                lp.boff = Vector((0.10 if up_side else 0.02, (0.06 if kind == 'H' else -0.06),
                                  0.04 if up_side else 0.10)) * hl
                lp.flex = (-70 if kind == 'F' else 40) * fold
                lp.toe = -25 * wb
                p.legs[(kind, s)] = lp
            return p
        return N, fn, False

    # ------------------------------------------------------------------ lying down
    def _lie(self, p, front, hind):
        sp, hl = self.sp, self.hl
        p.body = p.body + Vector((0, 0, -sp.LIE_DROP * (0.45 * front + 0.55 * hind)))
        p.pitch += 6.0 * (hind - front)
        for s in (1, -1):
            F0, H0 = self.neutral(('F', s)), self.neutral(('H', s))
            fl = LegPose(target=F0 + Vector((0.0, 0.02, -0.01)) * hl * front)
            fl.flex = -95 * front
            fl.toe = -15 * front
            fl.scap = -10 * front
            hl_ = LegPose(target=H0 + Vector((s * 0.10, -0.36, -0.01)) * hl * hind)
            hl_.flex = 95 * hind
            hl_.toe = -10 * hind
            p.legs[('F', s)] = fl
            p.legs[('H', s)] = hl_

    def _clip_sleep(self):
        n0 = 120
        N = self.N(n0)
        sp, hb = self.sp, self.hb
        pitches, head = sp.LIE_NECK

        def fn(f):
            p = self.pose()
            a = 2 * math.pi * f / N
            self._lie(p, 1.0, 1.0)
            p.body += Vector((0, 0, 0.008 * math.sin(a) * hb))
            p.spine[2][0] = 1.0 * math.sin(a)
            self._neck(p, pitches, (4, 4, 3))
            p.head = [head + 1.5 * math.sin(a), 4, 8]
            self._ears(p, -10, 10, flickR=_flick(f, self.F(n0, 70), 3, -30))
            self._tail(p, -4)
            return p
        return N, fn, True

    def _clip_wake(self):
        n0 = 60
        N = self.N(n0)
        sp, hb = self.sp, self.hb
        pitches, head = sp.LIE_NECK
        Kf = lambda keys, f: self.K(n0, keys, f)

        def fn(f):
            p = self.pose()
            t = f / N
            hind = 1 - ease(t / 0.50)
            front = 1 - ease((t - 0.30) / 0.55)
            self._lie(p, front, hind)
            p.body += Vector((0, Kf([(0, 0), (12, 0.06), (36, -0.03), (60, 0)], f) * hb, 0))
            sleepy = 1 - ease(t / 0.6)
            shake = Kf([(0, 0), (44, 0), (47, 1), (50, -1), (53, 0.6), (56, -0.2), (60, 0)], f)
            self._neck(p, [x * sleepy for x in pitches], (4 * sleepy, 4 * sleepy, 3 * sleepy))
            p.head = [head * sleepy, 4 * sleepy + 6 * shake, 8 * sleepy + 16 * shake]
            self._ears(p, -10 * sleepy, 10 * sleepy + 10 * abs(shake))
            self._tail(p, -4 * sleepy + 10 * abs(shake), 10 * shake)
            return p
        return N, fn, False

    # ------------------------------------------------------------------ build
    def build_clip(self, name, rig_ob=None):
        return BA.build_clip(self.SPEC, self.CLIPS, self.EVENTS, name, rig_ob)

    def build_clips(self, names=None):
        self.SPEC.rest.clear()
        return {n: self.build_clip(n) for n in (names or self.CLIPS)}

    def use(self, name, rig_ob=None):
        BA.use(self.SPEC, name, rig_ob)

    def clear(self, rig_ob=None):
        BA.clear(self.SPEC, rig_ob)


def for_species(sp):
    return FarmAnim(sp)
