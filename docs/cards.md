# Eggs, cards and pacts

## Eggs

Every defeated enemy drops an **egg** (`cards.drop_chance`: 100% for bats,
mini bats and bosses), coloured by its rarity: grey common, green uncommon,
blue rare, purple epic, yellow legendary, white mythical.

**Egg rarity** (`cards.rarity_weights`, weights for common … mythical):

| Source | common | uncommon | rare | epic | legendary | mythical |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| mini bat | 72 | 21 | 6 | 1 | 0 | 0 |
| bat | 64 | 24 | 8.5 | 3 | 0.4 | 0.04 |
| boss (3–5 eggs) | 10 | 40 | 35 | 12 | 2.5 | 0.3 |

Each bat tier above 1 shifts these a little towards rarer eggs
(`tier_shift`), and so does prestige (`prestige_scale`, through the
difficulty's prestige rules). Elites drop one rarity higher; the flock's
`egg_luck` (from cards and pacts, at most 25%) upgrades drops; a bird's
`luck` upgrades an egg it collects. None of these upgrades goes past
legendary: a mythical egg only drops as such, from its tiny weight (bats
0.0008, bosses 0.008), about once in 1000 runs.

Measured over 60 simulated runs before that change (expert bot, ~50 eggs per
run): 47% common, 29% uncommon, 15% rare, 6.6% epic, 2% legendary; a legendary
egg in one run out of three.

Picking an egg up **stops the game** and offers cards, listed top to bottom:
as many as the flock stat `choices` (3 to start, up to 6). **↑ / ↓** select,
**ENTER** takes. P still pauses.

**What an egg contains.** One card of the egg's rarity is guaranteed; every
other card rolls its own rarity from `cards.other_slots` (weights below). A
legendary egg has a legendary card, often an epic one and rares, never an
uncommon or a common one; an epic egg never has commons; a rare egg has
commons very rarely. Cards are shown rarest first and never repeat within an
egg.

| Egg | common | uncommon | rare | epic | legendary | mythical |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| common | 80 | 18 | 2 | 0 | 0 | 0 |
| uncommon | 55 | 35 | 9 | 1 | 0 | 0 |
| rare | 4 | 55 | 33 | 8 | 0 | 0 |
| epic | 0 | 30 | 50 | 18 | 2 | 0 |
| legendary | 0 | 0 | 45 | 45 | 10 | 0 |
| mythical | 0 | 0 | 15 | 45 | 35 | 5 |

Card effects are written for a common card and multiplied by
`cards.rarity_scale` for rarer ones: ×1, ×1.6, ×2.4, ×3.5, ×5, ×7.

## Cards

- **stat**: a permanent bonus for the whole flock.
- **boost**: a strong bonus for 20 seconds of game time.
- **powerup**: tailwind, wide cursor or timelapse; rarer ones last longer and are stronger.
- **training**: XP for every bird.
- **cursed** (☠): a big bonus with a drawback.
- **nest** (flock): a flock stat (more choices per egg, luck, prestige, rerolls).
- **bird** (⬯): hatch a bird of that rarity, only while a lane is free (a full
  flock gets no bird cards); White, Orange and Gold only if none is alive.
  The bird comes from the egg tables `eggs.rarity_candidates`: common
  Yellow / Red / Blue / Patchwork, uncommon Frosty / Poison / Berserk / Purple /
  Rock, rare Clockwork / Cookie / Stealth / Twister, epic White / Orange / Gold,
  legendary Dinosaur / Glitch, mythical Rainbow.

| Card | Kind | Duration | Rarities | What it does | At its lowest rarity | At its highest |
|---|---|---|---|---|---|---|
| **Sharp Beaks** | Flock bonus | Permanent | common – mythical | Every bird hits harder. | +6% damage | +42% damage |
| **Hollow Bones** | Flock bonus | Permanent | common – mythical | Birds climb faster. | +1.5 rising speed | +10.5 rising speed |
| **Feather Brake** | Flock bonus | Permanent | common – mythical | Birds fall more slowly: more time to bounce them. | −1.5 falling speed | −10.5 falling speed |
| **Keen Eyes** | Flock bonus | Permanent | common – mythical | More critical hits. | +3% crit chance | +21% crit chance |
| **Heavy Blows** | Flock bonus | Permanent | common – mythical | Critical hits hurt more. | +0.15 crit damage | +1.05 crit damage |
| **Brave Hearts** | Flock bonus | Permanent | common – mythical | Scared birds fall less fast. | +6% fear resistance | +42% fear resistance |
| **Steady Nerves** | Flock bonus | Permanent | common – mythical | Scares wear off sooner. | −6% fear duration | −42% fear duration |
| **Piercing Talons** | Flock bonus | Permanent | common – mythical | Ignore part of the armor of bats and barriers. | +2 armor pierce | +14 armor pierce |
| **Bat Hunter** | Flock bonus | Permanent | common – mythical | More damage against bats. | +6% damage vs bats | +42% damage vs bats |
| **Lumberjack** | Flock bonus | Permanent | common – mythical | More damage against obstacles. | +8% damage vs obstacles | +56% damage vs obstacles |
| **Giant Slayer** | Flock bonus | Permanent | uncommon – mythical | More damage against elites and bosses. | +12.8% damage vs elites | +56% damage vs elites |
| **Wide Wings** | Flock bonus | Permanent | common – mythical | Birds collect eggs from farther away. | +0.5 pickup radius | +3.5 pickup radius |
| **Lucky Feather** | Flock bonus | Permanent | common – mythical | An egg a bird collects may turn one rarity rarer. | +2% lucky finds (a collected egg turns rarer) | +14% lucky finds (a collected egg turns rarer) |
| **Quick Study** | Flock bonus | Permanent | common – mythical | Birds earn more XP from hits and kills. | +6% XP | +42% XP |
| **Show-off** | Flock bonus | Permanent | common – mythical | More points. | +5% score | +35% score |
| **Lasting Powers** | Flock bonus | Permanent | common – mythical | Powers last longer. | +8% power duration | +56% power duration |
| **Potent Powers** | Flock bonus | Permanent | common – mythical | Powers hit harder. | +8% power strength | +56% power strength |
| **Safety Net** | Flock bonus | Permanent | rare – mythical | A bird reaching the floor may bounce back instead. | +4.8% floor save | +14% floor save |
| **Second Wind** | Flock bonus | Permanent | legendary – mythical | Every bird can fire its power once more per ascent. | +1 power use per ascent | +1 power use per ascent |
| **Frenzy** | Boost | 20 s | common – mythical | A short burst of damage. | +40% damage | +280% damage |
| **Fearless** | Boost | 20 s | common – mythical | Bats may fail to scare the flock. | +25% fear immunity | +175% fear immunity |
| **Jet Stream** | Boost | 20 s | common – mythical | The flock shoots up. | +8 rising speed | +56 rising speed |
| **Golden Hour** | Boost | 20 s | common – mythical | More points for a while. | +40% score | +280% score |
| **Tailwind** | Power-up | 10 s | common – epic | A wind that lifts the whole flock. | Rising birds +10 speed<br>Falling birds −10 speed | Rising birds +30 speed<br>Falling birds −30 speed |
| **Wide Cursor** | Power-up | 10 s | common – epic | The cursor covers more lanes. | Bounce 3 lanes with one press | Bounce 5 lanes with one press |
| **Timelapse** | Power-up | 2 s | common – epic | Slow time down to catch falling birds. | The game runs 1.5× slower | The game runs 2× slower |
| **Training** | Training | Instant | common – mythical | XP for every bird right now. | +20 XP to every bird | +140 XP to every bird |
| **Glass Wings** | Cursed | Permanent | uncommon – mythical | Much more damage, but birds fall faster. | +24% damage<br>+3.2 falling speed | +105% damage<br>+14 falling speed |
| **Heavy Crown** | Cursed | Permanent | uncommon – mythical | Much more score, but birds rise more slowly. | +24% score<br>−3.2 rising speed | +105% score<br>−14 rising speed |
| **Reckless** | Cursed | Permanent | uncommon – mythical | More crits, but scares last longer. | +9.6% crit chance<br>+16% fear duration | +42% crit chance<br>+70% fear duration |
| **Blood Price** | Cursed | Permanent | rare – mythical | Stronger powers, but hitting things stuns longer. | +48% power strength<br>+36% impact stun | +140% power strength<br>+105% impact stun |
| **Gambler's Luck** | Cursed | Permanent | rare – mythical | Luckier finds, but a smaller pickup range. | +12% lucky finds (a collected egg turns rarer)<br>−0.96 pickup radius | +35% lucky finds (a collected egg turns rarer)<br>−2.8 pickup radius |
| **Four-leaf Clover** | Nest | Permanent | common – mythical | Luck: enemies drop rarer eggs. | +0.4% luck (rarer drops) | +2.8% luck (rarer drops) |
| **Fame** | Nest | Permanent | common – mythical | Fixed prestige for the flock: more score, rarer drops. | +0.4 prestige | +2.8 prestige |
| **Legend** | Nest | Permanent | epic – mythical | Multiplies the whole prestige of the flock. | +17.5% prestige | +35% prestige |
| **Second Chance** | Nest | Permanent | rare – mythical | One more egg reroll for this run. | +1 egg reroll this run | +1 egg reroll this run |
| **Escape Hatch** | Nest | Permanent | uncommon – rare | One more egg skip for this run. | +1 egg skip this run | +1 egg skip this run |
| **Wider Nest** | Nest | Permanent | epic – mythical | Every egg offers one more card. | +1 choice per egg | +1 choice per egg |
| **Lucky Nest** | Nest | Permanent | rare – mythical | Enemies drop rarer eggs. | +1.92% luck (rarer drops) | +5.6% luck (rarer drops) |

### Luck and prestige

- **Luck** (`egg_luck`, flock stat, at most 25%): the chance that an enemy
  drops an egg one rarity higher. Raised by Four-leaf Clover, Lucky Nest and
  some pacts. It changes drop rarities only.
- **Lucky finds** (`luck`, bird stat): the chance that an egg a bird collects
  turns one rarity higher (Glitch, Gold, Rainbow, Lucky Feather...).
- **Prestige** multiplies the score *and* pushes drops towards rarer eggs. It
  is `(1 + the prestige of every living bird + prestige_bonus) × prestige_mult`:
  **Fame** adds fixed prestige, the rarer **Legend** multiplies it.

### Reroll and skip

Each run starts with **3 rerolls** (R: new cards for the same egg) and
**3 skips** (S: leave the egg, take nothing), shown under the cards
(`cards.rerolls`, `cards.skips`). Second Chance and Escape Hatch give one more.
Pacts cannot be rerolled; they have Refuse instead.

## Pacts

After every biome boss the game stops again and offers 3 of that
boss's pacts (5–6 per boss), or **Refuse**. A pact is permanent: a boon and a
bane, multiplied by the boss's intensity (×1 / ×1.5 / ×2 / ×2.7 / ×3.5 / ×4.5
for bosses 1–6), so the pacts of later bosses are more extreme. Banes can also
change every bat that spawns from then on (more HP, defence, fear) or bring
more elites.

| Pact | After boss | What it does | Boon (×1) | Bane (×1) |
|---|:-:|---|---|---|
| **Blood Oath** | 1, 2, 5 | Strike harder, fall faster. | +15% damage | +2 falling speed |
| **Featherweight** | 1, 2 | Climb faster, but impacts stun longer. | +3 rising speed | +20% impact stun |
| **Greedy Nest** | 1, 3 | Rarer eggs, tougher bats. | +4% luck (rarer drops) | +10% bat HP |
| **Thick Skin** | 1 | Braver birds that climb more slowly. | +10% fear resistance | −1.5 rising speed |
| **Glass Cannon** | 1, 3, 6 | Deadly crits, longer scares. | +8% crit chance<br>+0.3 crit damage | +15% fear duration |
| **Hunter's Moon** | 2, 4 | Hunt elites: more of them, better drops. | +20% damage vs elites<br>+1.5% luck (rarer drops) | +3% elite bats |
| **Iron Will** | 2, 4 | Ignore scares, hit softer. | +8% fear immunity | −6% damage |
| **War Drums** | 2, 4, 6 | Stronger, longer powers; scarier bats. | +15% power strength<br>+15% power duration | +10% bat fear |
| **Tempest** | 2, 4 | Everything moves faster, up and down. | +3 rising speed | +3 falling speed |
| **Bat Plague** | 3, 5, 6 | More XP and score from tougher, more numerous elites. | +20% XP<br>+15% score | +12% bat HP<br>+3% elite bats |
| **Reaper** | 3, 4, 6 | Cut through armor, reach less far. | +5 armor pierce | −0.3 pickup radius |
| **Midas** | 3, 5, 6 | Gold and luck at the cost of damage. | +25% score<br>+3% lucky finds (a collected egg turns rarer) | −8% damage |
| **Wealth** | 4, 5 | Fortune favours you; bats grow thicker skin. | +5% lucky finds (a collected egg turns rarer)<br>+2% luck (rarer drops) | +4 bat defence |
| **Last Stand** | 5, 6 | Birds may survive the floor, but fight worse. | +5% floor save | −5% damage<br>+8% fear duration |

## Simulator

`tools/simulate.py` reports eggs opened, cards taken by rarity and kind, and
pacts made. The bot picks with `card_policy` (`smart`, `first`, `random`) and
`pact_policy` (`smart`, `refuse`, `random`), e.g. `--bot-set pact_policy=refuse`.

## Card levels and types followed

Each lasting card is a type with a level. Taking it again raises its level
(with the bonus of the rarity found) up to `card_max_level` (6) times a run,
and a run follows at most `card_types` (4) different types. Timed boosts,
power-ups, training and bird eggs are not limited. When a type is maxed it is
no longer offered; once a run follows its maximum of types only those come
back. When nothing lasting is left to offer and the flock has no free slot,
enemies drop no eggs until something frees up (a bird lost frees a slot).
The upgrades **Mastery** (+1 level, up to 10) and **Breadth** (+1 type, up to
7) raise the limits. Mythical cards are birds only; other cards stop at
legendary. With free slots an egg offers a bird often: always with 3 or more
free, 60% of the time with 1 or 2 (`cards.bird_chance_by_free_slots`).
