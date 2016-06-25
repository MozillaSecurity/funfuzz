/*
 * WebSpeech References
 *
 * Implementation: https://bugzilla.mozilla.org/show_bug.cgi?id=1003439
 * WebIDL:
    dom/webidl/SpeechGrammarList.webidl
    dom/webidl/SpeechGrammar.webidl
    dom/webidl/SpeechRecognitionAlternative.webidl
    dom/webidl/SpeechRecognitionError.webidl
    dom/webidl/SpeechRecognitionEvent.webidl
    dom/webidl/SpeechRecognitionResultList.webidl
    dom/webidl/SpeechRecognitionResult.webidl
    dom/webidl/SpeechRecognition.webidl
    dom/webidl/SpeechSynthesisErrorEvent.webidl
    dom/webidl/SpeechSynthesisEvent.webidl
    dom/webidl/SpeechSynthesisUtterance.webidl
    dom/webidl/SpeechSynthesisVoice.webidl
    dom/webidl/SpeechSynthesis.webidl
 * Mochitests: dom/media/webspeech/recognition/test
 *             dom/media/webspeech/synth/test
 * animation/test/css-animations
 * Specification: https://dvcs.w3.org/hg/speech-api/raw-file/tip/speechapi.html
 * MDN: https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API
 *
**/
var fuzzerWebSpeech = (function() {
  var utterances = [];
  var recognitions = [];
  var grammars = [];
  var grammarLists = [];
  var thingsToSay = ['Stop, Dave.', 'Would you like to play a game?', 'Destruct sequence engaged.', fuzzValues.texts];
  var thingsToGrammar = ["#JSGF V1.0; grammar test; public <simple> = hello ;"]; // XXX fuzz this...

  /*
  ** Main
  */
  var makeCommand = function(){
    var cmd = [];

    fuzzInternalErrorsAreBugs = false;
    Random.choose([
      [1, function(){
            // create an utterance
            var myutterance = Things.reserve();
            cmd.push(myutterance + ' = new SpeechSynthesisUtterance(' + Random.pick(utteranceAttributes.text) + ');');
            utterances.push(myutterance);
          }],
      [1, function(){
            // set attribute on an utterance
            if (!utterances.length) return;
            cmd.push(JS.setAttribute(Random.pick(utterances), utteranceAttributes) + ';');
          }],
      [1, function(){
            // call something on SpeechSynthesis
            cmd.push(JS.methodCall('window.speechSynthesis', synthMethods) + ';');
          }],
      [1, function(){
            // set an utterance event
            if (!utterances.length) return;
            cmd.push(Random.pick(utterances) + ".addEventListener" + JS.methodHead([simpleSource(Random.pick(utteranceEvents)), "function(e) { " + fuzzSubCommand() + "}"]) + ';');
          }],
/*
      [1, function(){
            // create a recognition
            var myrecognition = Things.reserve();
            cmd.push(myrecognition + ' = new SpeechRecognition();');
            recognitions.push(myrecognition);
          }],
      [1, function(){
            // set attribute on a recognition
            if (!recognitions.length) return;
            cmd.push(JS.setAttribute(Random.pick(recognitions), recognitionAttributes) + ';');
          }],
      [1, function(){
            // call something on SpeechRecognition
            if (!recognitions.length) return;
            cmd.push(JS.methodCall(Random.pick(recognitions), recognitionMethods) + ';');
          }],
      [1, function(){
            // set a recognition event
            if (!recognitions.length) return;
            cmd.push(Random.pick(recognitions) + ".addEventListener" + JS.methodHead([simpleSource(Random.pick(recognitionEvents)), "function(e) { " + fuzzSubCommand() + "}"]) + ';');
          }],
      [1, function(){
            // create a grammar
            var mygrammar = Things.reserve();
            cmd.push(mygrammar + ' = new SpeechGrammar();');
            grammars.push(mygrammar);
          }],
      [1, function(){
            // set attribute on a grammar
            var g = getGrammar();
            if (g === undefined) return;
            cmd.push(JS.setAttribute(g, grammarAttributes) + ';');
          }],
      [1, function(){
            // create a grammar list
            var mygrammarl = Things.reserve();
            cmd.push(mygrammarl + ' = new SpeechGrammarList();');
            grammarLists.push(mygrammarl);
          }],
      [1, function(){
            // call something on SpeechGrammarList
            if (!grammarLists.length) return;
            cmd.push(JS.methodCall(Random.pick(grammarLists), grammarListMethods) + ';');
          }],
*/
    ]);
    return cmd;
  };

  var getGrammar = function(){
    var poss = [];
    if (grammarLists.length)
      poss.push([10, function(){ var gl = Random.pick(grammarLists); return gl + '[' + rnd(1024) + '%' + gl + '.length]'; }]);
    if (grammars.length)
      poss.push([1, grammars]);
    if (!poss.length)
      return undefined;
    return Random.choose(poss);
  };

  var utteranceAttributes = {
    'text': function(){ return simpleSource((rnd(10) === 0) ? '' : Random.pick(thingsToSay)); },
    'lang': function(){ return simpleSource(Random.pick(fuzzValues.languages)); },
    'voiceURI': function() { if (rnd(32)===0) return simpleSource(Random.pick(fuzzValues.URIs)); return '(function(){var vl=window.speechSynthesis.getVoices();return vl['+rnd(1024)+'%vl.length].voiceURI;})()'; }, // XXX: get from window.speechSynthesis.getVoices() at runtime
    'volume': fuzzValues.numbers,
    'rate': fuzzValues.numbers,
    'pitch': fuzzValues.numbers
  };
  var recognitionAttributes = {
    'grammars': grammarLists,
    'lang': function(){ return simpleSource(Random.pick(fuzzValues.languages)); },
    'continuous': fuzzValues.booleans,
    'interimResults': fuzzValues.booleans,
    'maxAlternatives': fuzzValues.unsignedNumbers,
    'serviceURI': function(){ return simpleSource(Random.pick(fuzzValues.URIs)); } // XXX: improve?
  };
  var grammarAttributes = {
    //'src': , // XXX
    'weight': fuzzValues.numbers
  };

  var synthMethods = {
    'speak': [utterances],
    'cancel': [],
    'pause': [],
    'resume': [],
    'getVoices': []
  };
  var recognitionMethods = {
    'start': [],
    'stop': [],
    'abort': []
  };
  var grammarListMethods = {
    //'addFromURI': [], // XXX
    'addFromString': [thingsToGrammar, fuzzValues.numbers]
  };

  var utteranceEvents = [
    'start', 'end', 'error', 'pause', 'resume', 'mark', 'boundary'
  ];
  var recognitionEvents = [
    'audiostart', 'soundstart', 'speechstart', 'speechend', 'soundend', 'audioend', 'result', 'nomatch', 'error', 'start', 'end'
  ];

  return {
    makeCommand: makeCommand,
  };
})();

registerModule("fuzzerWebSpeech", 20);
