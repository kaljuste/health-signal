/* The body figure: one drawing for the habitat app and for the presenter's slides.
   HS_BODY.svg({ id, live, prefix, status, suit, label }) returns the SVG markup.
     id      id of the <svg> (the habitat app uses "fig")
     live    true adds the anchor layer and the click areas the habitat app needs
     prefix  put in front of the ids inside the drawing, so two figures can be on one page
     status  { region: "watch" | "warning" | "critical" } tints regions (the slides show an example day)
     suit    true draws a spacesuit outline around the body (the arm-unit slide)
   The twelve regions carry data-k: brain, mood, eyes, balance, lungs, heart, kidney, gut, bone, muscle, blood, skin.
   HS_BODY.anchor holds the point of each region that a label line ends on (same numbers as GROUPS in habitat.html). */
window.HS_BODY = (function () {
  const ART = `<defs>
  <path id="{p}s-head" d="M150 18C172 18 186 36 186 60C186 78 180 92 170 101C164 106 157 109 150 109C143 109 136 106 130 101C120 92 114 78 114 60C114 36 128 18 150 18Z"/>
  <!-- right half of the body (viewer's right), mirrored for the other side -->
  <path id="{p}s-half" d="M150 100L161 100C162 110 162 116 166 122C178 130 200 132 216 138C229 143 237 155 238 172C240 210 244 250 249 286C255 320 261 356 266 390C271 404 275 420 274 438C273 454 267 468 259 468C251 468 249 456 249 444C249 426 249 408 248 392C242 356 235 322 229 294C223 262 216 230 210 202C209 236 202 268 195 298C192 318 198 342 206 366C212 410 210 468 201 534C199 552 203 578 203 604C202 644 193 674 190 698C190 712 200 722 206 733C209 741 202 745 194 745L175 745C167 745 166 736 169 726C171 714 170 706 169 698C167 662 163 622 165 592C166 574 165 558 163 542C161 494 158 444 153 412L150 408"/>
  <clipPath id="{p}bodyClip">
    <use href="#{p}s-head"/><path d="M150 100L161 100C162 110 162 116 166 122C178 130 200 132 216 138C229 143 237 155 238 172C240 210 244 250 249 286C255 320 261 356 266 390C271 404 275 420 274 438C273 454 267 468 259 468C251 468 249 456 249 444C249 426 249 408 248 392C242 356 235 322 229 294C223 262 216 230 210 202C209 236 202 268 195 298C192 318 198 342 206 366C212 410 210 468 201 534C199 552 203 578 203 604C202 644 193 674 190 698C190 712 200 722 206 733C209 741 202 745 194 745L175 745C167 745 166 736 169 726C171 714 170 706 169 698C167 662 163 622 165 592C166 574 165 558 163 542C161 494 158 444 153 412L150 408Z"/>
    <path transform="translate(300 0) scale(-1 1)" d="M150 100L161 100C162 110 162 116 166 122C178 130 200 132 216 138C229 143 237 155 238 172C240 210 244 250 249 286C255 320 261 356 266 390C271 404 275 420 274 438C273 454 267 468 259 468C251 468 249 456 249 444C249 426 249 408 248 392C242 356 235 322 229 294C223 262 216 230 210 202C209 236 202 268 195 298C192 318 198 342 206 366C212 410 210 468 201 534C199 552 203 578 203 604C202 644 193 674 190 698C190 712 200 722 206 733C209 741 202 745 194 745L175 745C167 745 166 736 169 726C171 714 170 706 169 698C167 662 163 622 165 592C166 574 165 558 163 542C161 494 158 444 153 412L150 408Z"/>
  </clipPath>
  <pattern id="{p}scan" width="8" height="5" patternUnits="userSpaceOnUse"><rect width="8" height="1" fill="#1f1e1b"/></pattern>
  <radialGradient id="{p}aura" cx="50%" cy="40%" r="60%"><stop offset="0" stop-color="#1a1210"/><stop offset="1" stop-color="#1a1210" stop-opacity="0"/></radialGradient>
</defs>
<ellipse cx="150" cy="330" rx="170" ry="372" fill="url(#{p}aura)" opacity=".75"/>
{suit}<g class="body-fill" clip-path="url(#{p}bodyClip)"><rect width="300" height="760"/></g>
<rect width="300" height="760" fill="url(#{p}scan)" clip-path="url(#{p}bodyClip)"/>
<g class="body-line">
  <use href="#{p}s-head"/><use href="#{p}s-half"/><use href="#{p}s-half" transform="translate(300 0) scale(-1 1)"/>
</g>
<!-- quiet anatomy that is not a region -->
<g class="organ">
  <path d="M115 60C108 58 105 64 106 70C107 76 111 80 115 79"/>
  <path d="M150 128V156M150 156L143 164M150 156L157 164"/>
  <path d="M150 166V352" stroke-dasharray="2 5"/>
  <path d="M122 394L119 538M118 560L117 690"/><circle cx="118" cy="549" r="7"/>
  <path d="M182 560L183 690"/>
  <path d="M224 182C229 220 234 262 239 290C245 330 251 360 257 390"/>
  <path d="M166 122C160 132 156 136 150 138C144 136 140 132 134 122" opacity=".7"/>
</g>

<!-- regions: glyph (line art) + wash (status tint) -->
<g class="rg" data-k="brain">
  <path class="wash" d="M126 43C126 31 137 24 150 24C163 24 174 31 174 43C166 40 158 46 150 42C142 38 134 45 126 43Z"/>
  <path class="glyph" d="M126 43C126 31 137 24 150 24C163 24 174 31 174 43C166 40 158 46 150 42C142 38 134 45 126 43Z"/>
  <path class="glyph" d="M138 32c5-3 9 3 14 0M150 30c5-3 9 3 14 0"/>
</g>
<g class="rg" data-k="mood">
  <path class="wash" d="M126 47C134 49 142 42 150 46C158 50 166 44 174 47C174 55 166 61 150 61C134 61 126 55 126 47Z"/>
  <path class="glyph" d="M126 47C134 49 142 42 150 46C158 50 166 44 174 47C174 55 166 61 150 61C134 61 126 55 126 47Z"/>
  <path class="glyph" d="M137 54c5-3 9 2 13 0M152 54c5-3 8 2 12 0"/>
</g>
<g class="rg" data-k="eyes">
  <ellipse class="wash" cx="137" cy="73" rx="7" ry="4"/><ellipse class="wash" cx="163" cy="73" rx="7" ry="4"/>
  <ellipse class="glyph" cx="137" cy="73" rx="7" ry="4"/><ellipse class="glyph" cx="163" cy="73" rx="7" ry="4"/>
  <circle class="glyph" cx="137" cy="73" r="1.4"/><circle class="glyph" cx="163" cy="73" r="1.4"/>
</g>
<g class="rg" data-k="balance">
  <path class="wash" d="M185 58C192 56 196 62 195 69C194 76 190 81 185 80Z"/>
  <path class="glyph" d="M185 58C192 56 196 62 195 69C194 76 190 81 185 80"/>
  <path class="glyph" d="M187 66a3 3 0 1 1 0 6a2 2 0 1 1 1.6-3.2"/>
</g>
<g class="rg" data-k="lungs">
  <g class="breath">
    <path class="wash" d="M141 160C128 162 116 182 114 212C113 234 120 246 139 242C142 216 142 186 141 160Z"/>
    <path class="wash" d="M159 160C172 162 184 182 186 212C187 234 180 246 161 242C158 216 158 186 159 160Z"/>
    <path class="glyph" d="M141 160C128 162 116 182 114 212C113 234 120 246 139 242C142 216 142 186 141 160Z"/>
    <path class="glyph" d="M159 160C172 162 184 182 186 212C187 234 180 246 161 242C158 216 158 186 159 160Z"/>
  </g>
</g>
<g class="rg" data-k="heart">
  <path d="M164 198c3-7 14-6 14 3c0 8-8 13-14 19c-6-6-14-11-14-19c0-9 11-10 14-3Z" fill="#0a0a0a"/>
  <path class="wash" d="M164 198c3-7 14-6 14 3c0 8-8 13-14 19c-6-6-14-11-14-19c0-9 11-10 14-3Z"/>
  <path class="glyph" d="M164 198c3-7 14-6 14 3c0 8-8 13-14 19c-6-6-14-11-14-19c0-9 11-10 14-3Z"/>
  <circle class="beat" cx="164" cy="205" r="2.6"/>
</g>
<g class="rg" data-k="kidney">
  <path class="wash" d="M128 256c-7 0-10 7-9 14c1 7 5 11 10 10c-3-4-3-8 0-11c3-4 3-9-1-13Z"/>
  <path class="wash" d="M172 256c7 0 10 7 9 14c-1 7-5 11-10 10c3-4 3-8 0-11c-3-4-3-9 1-13Z"/>
  <path class="glyph" d="M128 256c-7 0-10 7-9 14c1 7 5 11 10 10c-3-4-3-8 0-11c3-4 3-9-1-13Z"/>
  <path class="glyph" d="M172 256c7 0 10 7 9 14c-1 7-5 11-10 10c3-4 3-8 0-11c-3-4-3-9 1-13Z"/>
</g>
<g class="rg" data-k="gut">
  <rect class="wash" x="127" y="290" width="46" height="56" rx="16"/>
  <rect class="glyph" x="127" y="290" width="46" height="56" rx="16"/>
  <path class="glyph" d="M137 304h24a7 7 0 0 1 0 14h-22a7 7 0 0 0 0 14h24"/>
</g>
<g class="rg" data-k="bone">
  <path class="wash" d="M112 362C124 350 142 352 150 364C158 352 176 350 188 362C184 380 170 392 150 396C130 392 116 380 112 362Z"/>
  <path class="glyph" d="M112 362C124 350 142 352 150 364C158 352 176 350 188 362C184 380 170 392 150 396C130 392 116 380 112 362Z"/>
  <circle class="glyph" cx="124" cy="386" r="7"/><circle class="glyph" cx="176" cy="386" r="7"/>
  <path class="glyph" d="M178 394L181 538"/><circle class="glyph" cx="182" cy="549" r="7"/>
  <path class="glyph" d="M146 176h8M146 200h8M146 224h8M146 248h8M146 272h8M146 352h8"/>
</g>
<g class="rg" data-k="muscle">
  <path class="wash" d="M106 596C102 624 105 648 110 662C113 670 120 670 123 662C128 646 131 622 128 596C122 589 112 589 106 596Z"/>
  <path class="wash" d="M99 430C95 470 98 500 104 516C108 526 115 526 119 516C125 498 128 468 125 430C118 422 106 422 99 430Z"/>
  <path class="glyph" d="M106 596C102 624 105 648 110 662C113 670 120 670 123 662C128 646 131 622 128 596C122 589 112 589 106 596Z"/>
  <path class="glyph" d="M99 430C95 470 98 500 104 516C108 526 115 526 119 516C125 498 128 468 125 430C118 422 106 422 99 430Z"/>
  <path class="glyph" d="M117 604V650M112 440V502"/>
</g>
<g class="rg" data-k="blood">
  <path class="glyph" d="M76 182C71 220 66 262 61 290C55 330 49 360 43 390C41 402 39 414 39 424"/>
  <path class="wash" d="M39 424c5 7 8 10 8 14a8 8 0 0 1-16 0c0-4 3-7 8-14Z"/>
  <path class="glyph" d="M39 424c5 7 8 10 8 14a8 8 0 0 1-16 0c0-4 3-7 8-14Z"/>
</g>
<g class="rg" data-k="skin">
  <path class="glyph" d="M226 606l-11 4M229 622h-12M226 638l-11-4"/>
  <circle class="wash" cx="199" cy="622" r="9"/>
  <circle class="glyph" cx="199" cy="622" r="9" stroke-dasharray="2 3"/>
</g>`;
  const LIVE = `<g id="anchors"></g>
<!-- hit areas: larger than the marks, keyboard reachable -->
<g id="hits">
  <path class="hit" data-k="skin" d="M210 140H236L276 400V470H244L206 200ZM164 560H232V744H168Z"/>
  <path class="hit" data-k="blood" d="M90 140H64L24 400V470H56L94 200Z"/>
  <path class="hit" data-k="muscle" d="M88 410H148L138 560H96ZM94 566H138V694H104Z"/>
  <rect class="hit" data-k="lungs" x="108" y="154" width="84" height="94"/>
  <rect class="hit" data-k="heart" x="147" y="188" width="34" height="36"/>
  <path class="hit" data-k="kidney" d="M114 250H140V286H114ZM160 250H186V286H160Z"/>
  <rect class="hit" data-k="gut" x="122" y="287" width="56" height="62"/>
  <rect class="hit" data-k="bone" x="106" y="350" width="88" height="54"/>
  <rect class="hit" data-k="brain" x="120" y="19" width="60" height="26"/>
  <rect class="hit" data-k="mood" x="120" y="45" width="60" height="19"/>
  <rect class="hit" data-k="eyes" x="126" y="65" width="48" height="16"/>
  <rect class="hit" data-k="balance" x="180" y="52" width="22" height="34"/>
</g>`;
  const SUIT = `<g class="suit-line"><circle cx="150" cy="62" r="62"/><use href="#{p}s-head"/><use href="#{p}s-half"/><use href="#{p}s-half" transform="translate(300 0) scale(-1 1)"/></g>`;
  const anchor = { brain: [138, 31], mood: [136, 54], lungs: [124, 202], blood: [39, 438], bone: [124, 386], muscle: [116, 610],
    balance: [190, 68], eyes: [163, 73], heart: [175, 213], kidney: [176, 268], gut: [166, 318], skin: [199, 622] };
  function svg(o) {
    o = o || {};
    const st = o.status || {};
    const art = ART.replace("{suit}", o.suit ? SUIT : "").replace(/\{p\}/g, o.prefix || "")
      .replace(/class="rg" data-k="(\w+)"/g, (m, k) => st[k] ? `class="rg ${st[k]}" data-k="${k}"` : m);
    return `<svg${o.id ? ` id="${o.id}"` : ""} viewBox="0 0 300 760" role="${o.live ? "group" : "img"}" aria-label="${o.label || "Body figure"}">\n${art}\n${o.live ? LIVE + "\n" : ""}</svg>`;
  }
  return { svg, anchor };
})();
