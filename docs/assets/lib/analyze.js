/* 규칙 기반 요약 — calllog/analyze.py 의 웹 버전.
 *
 * 외부 API·모델 없이 브라우저 안에서만 돌아가야 하므로 형태소 분석기 없이
 * 한국어 어절 패턴과 빈도로 뽑아낸다. 결과는 '읽을 거리' 수준의 발췌이며,
 * 원문 전체가 문서 뒤에 그대로 실리므로 빠뜨려도 정보가 사라지지 않는다.
 */
(function (global) {
  "use strict";

  var CallLog = (global.CallLog = global.CallLog || {});

  var SENT_SPLIT = /(?<=[.?!…])\s+|(?<=[다요죠네])\s+(?=[가-힣A-Za-z0-9])/g;
  var QUOTE_TRIM = " \"'“”‘’[]()";

  var STOPWORDS = new Set([
    "그리고", "그러면", "그래서", "그런데", "근데", "하지만", "저기", "일단", "그냥", "약간",
    "정말", "진짜", "너무", "많이", "조금", "다시", "이제", "지금", "오늘", "내일", "어제",
    "저희", "우리", "제가", "내가", "니가", "네가", "당신", "선생님", "사장님", "대표님",
    "이거", "그거", "저거", "여기", "거기", "저기", "이런", "그런", "저런", "어떤", "무슨",
    "네", "예", "응", "아니요", "아니", "맞아요", "맞습니다", "그렇죠", "그렇습니다",
    "있습니다", "있어요", "없습니다", "없어요", "합니다", "해요", "입니다", "이에요",
    "감사합니다", "고맙습니다", "수고", "안녕하세요", "혹시", "아마", "역시", "바로",
    "좀", "잘", "그게", "그건", "이건", "저건", "그럼", "그러니까", "그니까", "뭐",
    "하는", "있는", "없는", "같은", "다른", "이번", "지난", "다음", "관련", "대해서",
    "때문에", "경우", "부분", "생각", "이야기", "말씀", "거예요", "거죠", "겁니다",
    "오전", "오후", "전후", "정도", "건당", "그때", "이때", "현재", "대략",
    "이렇게", "그렇게", "저렇게", "먼저", "나중에", "그동안", "계속",
    "안에", "중으로", "이내", "내로", "쯤", "정도로", "관해서",
  ]);

  function trimQuotes(text) {
    var set = QUOTE_TRIM + " ";
    var out = String(text == null ? "" : text);
    while (out.length && set.indexOf(out.charAt(0)) >= 0) out = out.slice(1);
    while (out.length && set.indexOf(out.charAt(out.length - 1)) >= 0) out = out.slice(0, -1);
    return out;
  }

  function splitSentences(text) {
    var clean = String(text == null ? "" : text).replace(/\s{2,}/g, " ").trim();
    if (!clean) return [];
    var parts = [];
    var chunks = clean.split("\n");
    for (var c = 0; c < chunks.length; c++) {
      var chunk = chunks[c].trim();
      if (!chunk) continue;
      var pieces = chunk.split(SENT_SPLIT);
      for (var p = 0; p < pieces.length; p++) {
        var piece = trimQuotes(pieces[p]);
        if (CallLog.util.chars(piece).length >= 2) parts.push(piece);
      }
    }
    return parts;
  }

  function sentencesFrom(segments) {
    var out = [];
    for (var s = 0; s < segments.length; s++) {
      var seg = segments[s];
      var pieces = splitSentences(seg.text);
      if (!pieces.length) pieces = [String(seg.text).trim()];
      for (var i = 0; i < pieces.length; i++) {
        if (!pieces[i]) continue;
        out.push({
          text: pieces[i],
          speaker: seg.speaker || "",
          start: i === 0 ? seg.start : null,
          order: out.length,
        });
      }
    }
    return out;
  }

  /* ---------------------------------------------------------------- 키워드 */
  var TOKEN = /[가-힣]{2,}|[A-Za-z][A-Za-z0-9+#.-]{1,}|[0-9][0-9,]*/g;
  var VERB_TAIL =
    /(니다|습니|십니|했|됩|합니|하|할|한|해|되|된|돼|이고|인데|는데|지만|니까|면서|라고|다고|겠|세요|어요|아요|지요|나요|가요|네요|군요|게요|까요|죠|까|면|서|고|며|야|다|요)$/;

  // 조사·어미를 떼어 명사만 남긴다 (긴 것부터)
  var JOSA = [
    "이라서요", "이라서", "라서요", "라서", "이란", "라는", "이라고", "라고",
    "에서는", "에게서", "한테서", "으로부터", "로부터", "까지는", "부터는",
    "에게는", "한테는", "이라는", "이랑", "랑",
    "에서", "에게", "한테", "으로", "로는", "와는", "과는", "까지", "부터",
    "처럼", "보다", "마다", "조차", "밖에", "이나", "라도", "이라도",
    "은", "는", "이", "가", "을", "를", "의", "에", "도", "만", "와", "과",
    "로", "나", "든", "인",
  ].sort(function (a, b) {
    return b.length - a.length;
  });

  var UNIT_WORDS = new Set(["원", "만", "천", "억", "개", "명", "시", "분", "초", "번", "퍼센트", "프로", "달러"]);

  function stripJosa(token) {
    var out = token;
    var changed = true;
    while (changed) {
      changed = false;
      for (var i = 0; i < JOSA.length; i++) {
        var josa = JOSA[i];
        if (out.slice(-josa.length) === josa && out.length - josa.length >= 2) {
          out = out.slice(0, out.length - josa.length);
          changed = true;
          break;
        }
      }
    }
    return out;
  }

  function keywordOk(token) {
    if (token.length < 2) return false;
    if (STOPWORDS.has(token) || UNIT_WORDS.has(token)) return false;
    if (/^\d+$/.test(token)) return false;
    if (token.length <= 3 && /(까지|부터|처럼|보다|만큼)$/.test(token)) return false;
    if (VERB_TAIL.test(token)) return false;
    return true;
  }

  function keywords(text, limit) {
    var max = limit || 10;
    var counts = {};
    var firstSeen = {};
    var re = new RegExp(TOKEN.source, "g");
    var match;
    var index = 0;
    while ((match = re.exec(String(text == null ? "" : text))) !== null) {
      var token = stripJosa(match[0].replace(/^[.,\-"']+|[.,\-"']+$/g, ""));
      index += 1;
      if (!keywordOk(token)) continue;
      counts[token] = (counts[token] || 0) + 1;
      if (!(token in firstSeen)) firstSeen[token] = index;
    }
    var scored = [];
    for (var token2 in counts) {
      if (!Object.prototype.hasOwnProperty.call(counts, token2)) continue;
      var count = counts[token2];
      var weight = count * 2 + Math.min(CallLog.util.chars(token2).length, 6) * 0.4;
      if (count >= 2) weight += 1.5;
      scored.push({ weight: weight, order: firstSeen[token2], token: token2 });
    }
    if (!scored.length) return [];
    // 2회 이상 나온 말을 우선, 없으면 긴 단어(정보량 많음) 위주
    scored.sort(function (a, b) {
      if (b.weight !== a.weight) return b.weight - a.weight;
      return a.order - b.order;
    });
    // 서로 포함되는 단어는 긴 쪽만 남긴다 (예: '계약' / '계약서')
    var result = [];
    for (var i = 0; i < scored.length; i++) {
      var candidate = scored[i].token;
      var contained = false;
      for (var j = 0; j < result.length; j++) {
        if (candidate !== result[j] && result[j].indexOf(candidate) >= 0) {
          contained = true;
          break;
        }
      }
      if (contained) continue;
      result.push(candidate);
      if (result.length >= max) break;
    }
    return result;
  }

  /* ---------------------------------------------------------------- 금액·일정 */
  var AMOUNT = /(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)\s*(?:만\s*원|천\s*원|억\s*원|백\s*만\s*원|만|천|억|원|달러|불)/g;
  var DATE = new RegExp(
    "(\\d{4}년\\s*\\d{1,2}월\\s*\\d{1,2}일|\\d{1,2}월\\s*\\d{1,2}일|" +
      "\\d{4}[-./]\\s*\\d{1,2}[-./]\\s*\\d{1,2}|" +
      "(?:오늘|내일|모레|글피|이번\\s*주|다음\\s*주|다다음\\s*주|이번\\s*달|다음\\s*달)[^\\s,.]*|" +
      "(?:월|화|수|목|금|토|일)요일|" +
      "(?:오전|오후)\\s*\\d{1,2}\\s*시(?:\\s*\\d{1,2}\\s*분)?|" +
      "\\d{1,2}\\s*시(?:\\s*\\d{1,2}\\s*분)?(?:\\s*(?:까지|에|쯤))?)",
    "g"
  );
  var DUE = new RegExp(
    "((?:\\d{4}년\\s*)?\\d{1,2}월\\s*\\d{1,2}일(?:\\s*(?:까지|전|안으로))?|" +
      "\\d{1,2}\\s*일(?:\\s*까지|내로)?|" +
      "(?:오늘|내일|모레|이번\\s*주|다음\\s*주|다음\\s*달)[^\\s,.]*?(?:까지|안으로)?|" +
      "(?:월|화|수|목|금|토|일)요일(?:\\s*까지)?|" +
      "(?:오전|오후)?\\s*\\d{1,2}\\s*시(?:\\s*\\d{1,2}\\s*분)?(?:\\s*까지)?)"
  );

  function unique(items, limit) {
    var max = limit || 6;
    var out = [];
    for (var i = 0; i < items.length; i++) {
      var item = String(items[i]).replace(/\s{2,}/g, " ").trim();
      if (!item) continue;
      var dup = false;
      for (var j = 0; j < out.length; j++) {
        if (item === out[j] || out[j].indexOf(item) >= 0) {
          dup = true;
          break;
        }
      }
      if (dup) continue;
      out.push(item);
      if (out.length >= max) break;
    }
    return out;
  }

  function findAll(pattern, text) {
    var re = new RegExp(pattern.source, "g");
    var out = [];
    var m;
    while ((m = re.exec(String(text == null ? "" : text))) !== null) {
      out.push(m[0].trim());
      if (m[0] === "") re.lastIndex += 1;
    }
    return out;
  }

  function amountsIn(text, limit) {
    return unique(findAll(AMOUNT, text), limit);
  }

  function datesIn(text, limit) {
    return unique(findAll(DATE, text), limit);
  }

  /* ---------------------------------------------------------------- 중요도 점수 */
  var REQUEST =
    /(해\s*주|해\s*줘|해줘|부탁|요청|보내\s*주|보내줘|보내\s*줄|보내\s*드리|보낼게|보내겠|확인해|확인\s*부탁|연락\s*주|연락해|연락\s*줄|알려\s*주|알려줘|전달해|공유해|준비해|정리해|검토해|결제해|송금해|취소해|수정해|발주해|서명해|맡아|맡을|챙겨|챙기|주시면|주세요|주실|주실래|가능할까요|가능한가요|괜찮으세요|어떠세요|어떨까요|확인\s*가능)/;
  var COMMIT =
    /(할게요|할게|하겠습니다|하겠어요|하기로|하기로\s*했|할\s*예정|할\s*것입니다|할\s*거예요|할\s*겁니다|보낼게|보내겠|보내드릴|보내\s*드릴|드릴게|연락드릴|연락\s*드릴|확인할게|확인하겠|준비할게|준비하겠|정리할게|정리해서|챙길게|챙기겠|맞춰\s*볼게|알려드릴|올릴게|올리겠|맡을게|맡겠|맡을게요)/;
  var DECISION = /(결정|확정|하기로|로\s*하죠|로\s*합시다|로\s*할게요|그렇게\s*하죠|진행하)/i;
  var PLEASANTRY =
    /^(?:네|예|아|어|음)?[,\s]*(?:잘\s*)?(?:부탁(?:드립니다|드려요|해요|합니다)|수고(?:하셨습니다|하세요|많으셨습니다)|감사합니다|고맙습니다|좋은\s*(?:저녁|하루|주말|밤)|안녕히\s*계세요)[.!]?$/;

  function test(pattern, text) {
    var re = new RegExp(pattern.source, pattern.flags);
    return re.test(text);
  }

  function score(sentence, keywordSet) {
    var text = sentence.text;
    var value = 0;
    if (test(AMOUNT, text)) value += 3.0;
    if (test(DATE, text)) value += 2.0;
    // 요청·약속은 한 문장에서 겹쳐 세지 않는다 (점수 인플레 방지)
    if (test(REQUEST, text) || test(COMMIT, text)) value += 2.2;
    if (DECISION.test(text)) value += 1.0;
    if (text.indexOf("?") >= 0) value += 1.0;
    var hits = 0;
    keywordSet.forEach(function (kw) {
      if (text.indexOf(kw) >= 0) hits += 1;
    });
    value += Math.min(hits, 3) * 0.6;
    var length = CallLog.util.chars(text).length;
    if (length < 8) value -= 1.0;
    else if (length > 120) value -= 0.5;
    return value;
  }

  function tooSimilar(a, b, threshold) {
    var limit = threshold || 0.72;
    if (!a || !b) return false;
    if (a.indexOf(b) >= 0 || b.indexOf(a) >= 0) return true;
    var ta = new Set(findAll(TOKEN, a));
    var tb = new Set(findAll(TOKEN, b));
    if (!ta.size || !tb.size) return false;
    var overlap = 0;
    ta.forEach(function (token) {
      if (tb.has(token)) overlap += 1;
    });
    return overlap / Math.min(ta.size, tb.size) >= limit;
  }

  function summarize(segments, limit, keywordList) {
    var max = limit || 5;
    var sents = sentencesFrom(segments);
    if (!sents.length) return [];
    var kwSet = new Set(
      keywordList && keywordList.length
        ? keywordList
        : keywords(
            sents
              .map(function (s) {
                return s.text;
              })
              .join(" "),
            12
          )
    );
    var ranked = sents.slice().sort(function (a, b) {
      var diff = score(b, kwSet) - score(a, kwSet);
      if (diff !== 0) return diff;
      return a.order - b.order;
    });
    var picked = [];
    for (var i = 0; i < ranked.length; i++) {
      var sent = ranked[i];
      if (score(sent, kwSet) <= 0 && picked.length) continue;
      var similar = false;
      for (var j = 0; j < picked.length; j++) {
        if (tooSimilar(sent.text, picked[j].text)) {
          similar = true;
          break;
        }
      }
      if (similar) continue;
      picked.push(sent);
      if (picked.length >= max) break;
    }
    picked.sort(function (a, b) {
      return a.order - b.order;
    });
    return picked.map(function (s) {
      return s.text;
    });
  }

  function extractActions(segments, limit, speakers) {
    var max = limit || 8;
    var sents = sentencesFrom(segments);
    var items = [];
    var seen = new Set();
    for (var i = 0; i < sents.length; i++) {
      var sent = sents[i];
      var text = trimQuotes(sent.text);
      if (text.length < 5) continue;
      var request = test(REQUEST, text);
      var commit = test(COMMIT, text);
      if (!request && !commit) continue;
      if (PLEASANTRY.test(text)) continue;
      var norm = text.replace(/[\s.,!?]/g, "");
      if (seen.has(norm)) continue;
      seen.add(norm);
      var dueMatch = new RegExp(DUE.source).exec(text);
      items.push({
        text: text,
        owner: commit ? sent.speaker : "",
        due: dueMatch ? dueMatch[0].trim() : "",
        speaker: sent.speaker,
      });
      if (items.length >= max) break;
    }
    return items;
  }

  CallLog.analyze = {
    splitSentences: splitSentences,
    sentencesFrom: sentencesFrom,
    keywords: keywords,
    summarize: summarize,
    extractActions: extractActions,
    amountsIn: amountsIn,
    datesIn: datesIn,
    stripJosa: stripJosa,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
