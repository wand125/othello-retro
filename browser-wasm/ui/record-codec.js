/* Versioned, unpadded Base64URL game records. Forced passes are reconstructed. */
"use strict";
(() => {
  const emptySquares=()=>Array.from({length:64},(_,square)=>square).filter(square=>![27,28,35,36].includes(square));
  const fail=()=>{throw Error("共有された棋譜の形式が正しくありません。");};
  function encode(moves) {
    if(!Array.isArray(moves) || moves.length>120 || moves.some(move=>typeof move!=="string" || !/^(?:[a-h][1-8]|pass)$/.test(move)))return fail();
    const placements=moves.filter(move=>move!=="pass"),available=emptySquares();
    if(placements.length>60)return fail();
    let rank=0n;
    for(const move of placements){
      const square=(Number(move[1])-1)*8+"abcdefgh".indexOf(move[0]),choice=available.indexOf(square);
      if(choice<0)return fail();
      rank=rank*BigInt(available.length)+BigInt(choice);available.splice(choice,1);
    }
    const digits=[];do{digits.unshift(Number(rank&255n));rank>>=8n;}while(rank);
    // Version + placement count + mixed-radix rank; at most 37 bytes / 50 chars.
    const bytes=[1,placements.length,...digits];
    const code=btoa(String.fromCharCode(...bytes)).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
    if(code.length>60)return fail();
    return code;
  }
  function decode(code) {
    if(typeof code!=="string" || code.length<4 || code.length>60 || !/^[A-Za-z0-9_-]+$/.test(code))return fail();
    let bytes;
    try{bytes=Uint8Array.from(atob(code.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-code.length%4)%4)),char=>char.charCodeAt(0));}catch{return fail();}
    if(bytes.length<3 || bytes[0]!==1 || bytes[1]>60 || (bytes.length>3 && bytes[2]===0))return fail();
    const count=bytes[1],choices=Array(count),available=emptySquares();
    let rank=0n;for(const value of bytes.slice(2))rank=(rank<<8n)|BigInt(value);
    for(let i=count-1;i>=0;i--){const radix=BigInt(60-i);choices[i]=Number(rank%radix);rank/=radix;}
    if(rank!==0n)return fail();
    const moves=choices.map(choice=>{const square=available.splice(choice,1)[0];return "abcdefgh"[square%8]+(Math.floor(square/8)+1);});
    if(encode(moves)!==code)return fail();
    return moves;
  }
  const codec=Object.freeze({encode,decode,maxLength:60,version:1});
  globalThis.OthelloRecordCodec=codec;
  if(typeof module!=="undefined" && module.exports)module.exports=codec;
})();
