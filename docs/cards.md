# Eggs, cards and pacts

## Eggs

Every enemy drop is an **egg** coloured by its rarity: grey common, green
uncommon, blue rare, purple epic, yellow legendary, white mythical. Bats drop
one 55% of the time, mini bats 25%, bosses always (`cards.drop_chance`). The
rarity is rolled as before (prestige pushes it up); a bird's `luck` can
upgrade an egg it collects, and the flock's `egg_luck` upgrades drops.

Picking an egg up **stops the game** and offers cards: as many as the flock
stat `choices` (3 to start, up to 6). LEFT / RIGHT select, UP or SPACE take
(confirm keys are ignored for the first half second, so a press meant for a
bird does not take a card). P still pauses.

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
- **boost**: a strong bonus for 20 seconds.
- **powerup**: tailwind, wide cursor or timelapse (stronger at higher rarity).
- **training**: XP for every bird.
- **cursed** (☠): a big bonus with a drawback.
- **flock**: a flock stat (more choices per egg, luckier drops).
- **bird** (⬯): hatch a bird of that rarity, only while a lane is free (a full
  flock gets no bird cards); White, Orange and Gold only if none is alive.
  The bird comes from the egg tables `eggs.rarity_candidates`: common
  Yellow / Red / Blue / Patchwork, uncommon Frosty / Poison / Berserk / Purple /
  Rock, rare Clockwork / Cookie / Stealth / Twister, epic White / Orange / Gold,
  legendary Dinosaur / Glitch, mythical Rainbow.

| Card | Kind | Rarities | At its lowest rarity | At its highest |
|---|---|---|---|---|
| Sharp Beaks | stat | common – mythical | +6% damage | +42% damage |
| Hollow Bones | stat | common – mythical | +1.5 rising speed | +10.5 rising speed |
| Feather Brake | stat | common – mythical | −1.5 falling speed | −10.5 falling speed |
| Keen Eyes | stat | common – mythical | +3% crit chance | +21% crit chance |
| Heavy Blows | stat | common – mythical | +0.15 crit damage | +1.05 crit damage |
| Brave Hearts | stat | common – mythical | +6% fear resistance | +42% fear resistance |
| Steady Nerves | stat | common – mythical | −6% fear duration | −42% fear duration |
| Piercing Talons | stat | common – mythical | +2 armor pierce | +14 armor pierce |
| Bat Hunter | stat | common – mythical | +6% damage vs bats | +42% damage vs bats |
| Lumberjack | stat | common – mythical | +8% damage vs obstacles | +56% damage vs obstacles |
| Giant Slayer | stat | uncommon – mythical | +12.8% damage vs elites | +56% damage vs elites |
| Wide Wings | stat | common – mythical | +0.5 pickup radius | +3.5 pickup radius |
| Lucky Feather | stat | common – mythical | +2% luck | +14% luck |
| Quick Study | stat | common – mythical | +6% XP | +42% XP |
| Show-off | stat | common – mythical | +5% score | +35% score |
| Lasting Powers | stat | common – mythical | +8% power duration | +56% power duration |
| Potent Powers | stat | common – mythical | +8% power strength | +56% power strength |
| Safety Net | stat | rare – mythical | +4.8% floor save | +14% floor save |
| Second Wind | stat | legendary – mythical | +1 power use per ascent | +1 power use per ascent |
| Frenzy | boost | common – mythical | +40% damage for 20 s | +280% damage for 20 s |
| Fearless | boost | common – mythical | +25% fear immunity for 20 s | +175% fear immunity for 20 s |
| Jet Stream | boost | common – mythical | +8 rising speed for 20 s | +56 rising speed for 20 s |
| Golden Hour | boost | common – mythical | +40% score for 20 s | +280% score for 20 s |
| Tailwind | powerup | common – epic | Tailwind: the flock rises faster | Tailwind: the flock rises faster |
| Wide Cursor | powerup | common – epic | Wide cursor: bounce more lanes at once | Wide cursor: bounce more lanes at once |
| Timelapse | powerup | common – epic | Timelapse: the game slows down | Timelapse: the game slows down |
| Training | training | common – mythical | +20 XP to every bird | +140 XP to every bird |
| Glass Wings | cursed | uncommon – mythical | +24% damage; +3.2 falling speed | +105% damage; +14 falling speed |
| Heavy Crown | cursed | uncommon – mythical | +24% score; −3.2 rising speed | +105% score; −14 rising speed |
| Reckless | cursed | uncommon – mythical | +9.6% crit chance; +16% fear duration | +42% crit chance; +70% fear duration |
| Blood Price | cursed | rare – mythical | +48% power strength; +36% impact stun | +140% power strength; +105% impact stun |
| Gambler's Luck | cursed | rare – mythical | +12% luck; −0.96 pickup radius | +35% luck; −2.8 pickup radius |
| Wider Nest | flock | epic – mythical | +1 choice per egg | +1 choice per egg |
| Lucky Nest | flock | rare – mythical | +4.8% rarer drops | +14% rarer drops |

## Pacts

After every biome boss the game stops again and offers 3 of that
boss's pacts (5–6 per boss), or **Refuse**. A pact is permanent: a boon and a
bane, multiplied by the boss's intensity (×1 / ×1.5 / ×2 / ×2.7 / ×3.5 / ×4.5
for bosses 1–6), so the pacts of later bosses are more extreme. Banes can also
change every bat that spawns from then on (more HP, defence, fear) or bring
more elites.

| Pact | After boss | Boon (×1) | Bane (×1) |
|---|:-:|---|---|
| Blood Oath | 1, 2, 5 | +15% damage | +2 falling speed |
| Featherweight | 1, 2 | +3 rising speed | +20% impact stun |
| Greedy Nest | 1, 3 | +8% rarer drops | +10% bat HP |
| Thick Skin | 1 | +10% fear resistance | −1.5 rising speed |
| Glass Cannon | 1, 3, 6 | +8% crit chance; +0.3 crit damage | +15% fear duration |
| Hunter's Moon | 2, 4 | +20% damage vs elites; +3% rarer drops | +3% elite bats |
| Iron Will | 2, 4 | +8% fear immunity | −6% damage |
| War Drums | 2, 4, 6 | +15% power strength; +15% power duration | +10% bat fear |
| Tempest | 2, 4 | +3 rising speed | +3 falling speed |
| Bat Plague | 3, 5, 6 | +20% XP; +15% score | +12% bat HP; +3% elite bats |
| Reaper | 3, 4, 6 | +5 armor pierce | −0.3 pickup radius |
| Midas | 3, 5, 6 | +25% score; +3% luck | −8% damage |
| Wealth | 4, 5 | +5% luck; +4% rarer drops | +4 bat defence |
| Last Stand | 5, 6 | +5% floor save | −5% damage; +8% fear duration |

## Simulator

`tools/simulate.py` reports eggs opened, cards taken by rarity and kind, and
pacts made. The bot picks with `card_policy` (`smart`, `first`, `random`) and
`pact_policy` (`smart`, `refuse`, `random`), e.g. `--bot-set pact_policy=refuse`.
