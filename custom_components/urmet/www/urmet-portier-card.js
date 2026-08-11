console.info("%c URMET-PORTIER-CARD %c 0.2.0 ","background:#1e88e5;color:#fff;border-radius:3px","");const t=globalThis,e=t.ShadowRoot&&(void 0===t.ShadyCSS||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,i=Symbol(),s=new WeakMap;let n=class{constructor(t,e,s){if(this._$cssResult$=!0,s!==i)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=e}get styleSheet(){let t=this.o;const i=this.t;if(e&&void 0===t){const e=void 0!==i&&1===i.length;e&&(t=s.get(i)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),e&&s.set(i,t))}return t}toString(){return this.cssText}};const r=(t,...e)=>{const s=1===t.length?t[0]:e.reduce((e,i,s)=>e+(t=>{if(!0===t._$cssResult$)return t.cssText;if("number"==typeof t)return t;throw Error("Value passed to 'css' function must be a 'css' function result: "+t+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(i)+t[s+1],t[0]);return new n(s,t,i)},o=e?t=>t:t=>t instanceof CSSStyleSheet?(t=>{let e="";for(const i of t.cssRules)e+=i.cssText;return(t=>new n("string"==typeof t?t:t+"",void 0,i))(e)})(t):t,{is:a,defineProperty:c,getOwnPropertyDescriptor:h,getOwnPropertyNames:l,getOwnPropertySymbols:d,getPrototypeOf:u}=Object,p=globalThis,g=p.trustedTypes,m=g?g.emptyScript:"",f=p.reactiveElementPolyfillSupport,_=(t,e)=>t,v={toAttribute(t,e){switch(e){case Boolean:t=t?m:null;break;case Object:case Array:t=null==t?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=null!==t;break;case Number:i=null===t?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch(t){i=null}}return i}},$=(t,e)=>!a(t,e),y={attribute:!0,type:String,converter:v,reflect:!1,useDefault:!1,hasChanged:$};Symbol.metadata??=Symbol("metadata"),p.litPropertyMetadata??=new WeakMap;let b=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,e=y){if(e.state&&(e.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((e=Object.create(e)).wrapped=!0),this.elementProperties.set(t,e),!e.noAccessor){const i=Symbol(),s=this.getPropertyDescriptor(t,i,e);void 0!==s&&c(this.prototype,t,s)}}static getPropertyDescriptor(t,e,i){const{get:s,set:n}=h(this.prototype,t)??{get(){return this[e]},set(t){this[e]=t}};return{get:s,set(e){const r=s?.call(this);n?.call(this,e),this.requestUpdate(t,r,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??y}static _$Ei(){if(this.hasOwnProperty(_("elementProperties")))return;const t=u(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(_("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(_("properties"))){const t=this.properties,e=[...l(t),...d(t)];for(const i of e)this.createProperty(i,t[i])}const t=this[Symbol.metadata];if(null!==t){const e=litPropertyMetadata.get(t);if(void 0!==e)for(const[t,i]of e)this.elementProperties.set(t,i)}this._$Eh=new Map;for(const[t,e]of this.elementProperties){const i=this._$Eu(t,e);void 0!==i&&this._$Eh.set(i,t)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const e=[];if(Array.isArray(t)){const i=new Set(t.flat(1/0).reverse());for(const t of i)e.unshift(o(t))}else void 0!==t&&e.push(o(t));return e}static _$Eu(t,e){const i=e.attribute;return!1===i?void 0:"string"==typeof i?i:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,e=this.constructor.elementProperties;for(const i of e.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const i=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return((i,s)=>{if(e)i.adoptedStyleSheets=s.map(t=>t instanceof CSSStyleSheet?t:t.styleSheet);else for(const e of s){const s=document.createElement("style"),n=t.litNonce;void 0!==n&&s.setAttribute("nonce",n),s.textContent=e.cssText,i.appendChild(s)}})(i,this.constructor.elementStyles),i}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,e,i){this._$AK(t,i)}_$ET(t,e){const i=this.constructor.elementProperties.get(t),s=this.constructor._$Eu(t,i);if(void 0!==s&&!0===i.reflect){const n=(void 0!==i.converter?.toAttribute?i.converter:v).toAttribute(e,i.type);this._$Em=t,null==n?this.removeAttribute(s):this.setAttribute(s,n),this._$Em=null}}_$AK(t,e){const i=this.constructor,s=i._$Eh.get(t);if(void 0!==s&&this._$Em!==s){const t=i.getPropertyOptions(s),n="function"==typeof t.converter?{fromAttribute:t.converter}:void 0!==t.converter?.fromAttribute?t.converter:v;this._$Em=s;const r=n.fromAttribute(e,t.type);this[s]=r??this._$Ej?.get(s)??r,this._$Em=null}}requestUpdate(t,e,i,s=!1,n){if(void 0!==t){const r=this.constructor;if(!1===s&&(n=this[t]),i??=r.getPropertyOptions(t),!((i.hasChanged??$)(n,e)||i.useDefault&&i.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(r._$Eu(t,i))))return;this.C(t,e,i)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,e,{useDefault:i,reflect:s,wrapped:n},r){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,r??e??this[t]),!0!==n||void 0!==r)||(this._$AL.has(t)||(this.hasUpdated||i||(e=void 0),this._$AL.set(t,e)),!0===s&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t){Promise.reject(t)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[t,e]of this._$Ep)this[t]=e;this._$Ep=void 0}const t=this.constructor.elementProperties;if(t.size>0)for(const[e,i]of t){const{wrapped:t}=i,s=this[e];!0!==t||this._$AL.has(e)||void 0===s||this.C(e,void 0,i,s)}}let t=!1;const e=this._$AL;try{t=this.shouldUpdate(e),t?(this.willUpdate(e),this._$EO?.forEach(t=>t.hostUpdate?.()),this.update(e)):this._$EM()}catch(e){throw t=!1,this._$EM(),e}t&&this._$AE(e)}willUpdate(t){}_$AE(t){this._$EO?.forEach(t=>t.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(t=>this._$ET(t,this[t])),this._$EM()}updated(t){}firstUpdated(t){}};b.elementStyles=[],b.shadowRootOptions={mode:"open"},b[_("elementProperties")]=new Map,b[_("finalized")]=new Map,f?.({ReactiveElement:b}),(p.reactiveElementVersions??=[]).push("2.1.2");const A=globalThis,w=t=>t,S=A.trustedTypes,k=S?S.createPolicy("lit-html",{createHTML:t=>t}):void 0,C="$lit$",x=`lit$${Math.random().toFixed(9).slice(2)}$`,E="?"+x,U=`<${E}>`,P=document,T=()=>P.createComment(""),R=t=>null===t||"object"!=typeof t&&"function"!=typeof t,M=Array.isArray,I="[ \t\n\f\r]",O=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,H=/-->/g,N=/>/g,D=RegExp(`>|${I}(?:([^\\s"'>=/]+)(${I}*=${I}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,"g"),L=/'/g,z=/"/g,j=/^(?:script|style|textarea|title)$/i,q=(t=>(e,...i)=>({_$litType$:t,strings:e,values:i}))(1),G=Symbol.for("lit-noChange"),W=Symbol.for("lit-nothing"),B=new WeakMap,V=P.createTreeWalker(P,129);function F(t,e){if(!M(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==k?k.createHTML(e):e}const J=(t,e)=>{const i=t.length-1,s=[];let n,r=2===e?"<svg>":3===e?"<math>":"",o=O;for(let e=0;e<i;e++){const i=t[e];let a,c,h=-1,l=0;for(;l<i.length&&(o.lastIndex=l,c=o.exec(i),null!==c);)l=o.lastIndex,o===O?"!--"===c[1]?o=H:void 0!==c[1]?o=N:void 0!==c[2]?(j.test(c[2])&&(n=RegExp("</"+c[2],"g")),o=D):void 0!==c[3]&&(o=D):o===D?">"===c[0]?(o=n??O,h=-1):void 0===c[1]?h=-2:(h=o.lastIndex-c[2].length,a=c[1],o=void 0===c[3]?D:'"'===c[3]?z:L):o===z||o===L?o=D:o===H||o===N?o=O:(o=D,n=void 0);const d=o===D&&t[e+1].startsWith("/>")?" ":"";r+=o===O?i+U:h>=0?(s.push(a),i.slice(0,h)+C+i.slice(h)+x+d):i+x+(-2===h?e:d)}return[F(t,r+(t[i]||"<?>")+(2===e?"</svg>":3===e?"</math>":"")),s]};class K{constructor({strings:t,_$litType$:e},i){let s;this.parts=[];let n=0,r=0;const o=t.length-1,a=this.parts,[c,h]=J(t,e);if(this.el=K.createElement(c,i),V.currentNode=this.el.content,2===e||3===e){const t=this.el.content.firstChild;t.replaceWith(...t.childNodes)}for(;null!==(s=V.nextNode())&&a.length<o;){if(1===s.nodeType){if(s.hasAttributes())for(const t of s.getAttributeNames())if(t.endsWith(C)){const e=h[r++],i=s.getAttribute(t).split(x),o=/([.?@])?(.*)/.exec(e);a.push({type:1,index:n,name:o[2],strings:i,ctor:"."===o[1]?tt:"?"===o[1]?et:"@"===o[1]?it:Y}),s.removeAttribute(t)}else t.startsWith(x)&&(a.push({type:6,index:n}),s.removeAttribute(t));if(j.test(s.tagName)){const t=s.textContent.split(x),e=t.length-1;if(e>0){s.textContent=S?S.emptyScript:"";for(let i=0;i<e;i++)s.append(t[i],T()),V.nextNode(),a.push({type:2,index:++n});s.append(t[e],T())}}}else if(8===s.nodeType)if(s.data===E)a.push({type:2,index:n});else{let t=-1;for(;-1!==(t=s.data.indexOf(x,t+1));)a.push({type:7,index:n}),t+=x.length-1}n++}}static createElement(t,e){const i=P.createElement("template");return i.innerHTML=t,i}}function Z(t,e,i=t,s){if(e===G)return e;let n=void 0!==s?i._$Co?.[s]:i._$Cl;const r=R(e)?void 0:e._$litDirective$;return n?.constructor!==r&&(n?._$AO?.(!1),void 0===r?n=void 0:(n=new r(t),n._$AT(t,i,s)),void 0!==s?(i._$Co??=[])[s]=n:i._$Cl=n),void 0!==n&&(e=Z(t,n._$AS(t,e.values),n,s)),e}class Q{constructor(t,e){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=e}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:e},parts:i}=this._$AD,s=(t?.creationScope??P).importNode(e,!0);V.currentNode=s;let n=V.nextNode(),r=0,o=0,a=i[0];for(;void 0!==a;){if(r===a.index){let e;2===a.type?e=new X(n,n.nextSibling,this,t):1===a.type?e=new a.ctor(n,a.name,a.strings,this,t):6===a.type&&(e=new st(n,this,t)),this._$AV.push(e),a=i[++o]}r!==a?.index&&(n=V.nextNode(),r++)}return V.currentNode=P,s}p(t){let e=0;for(const i of this._$AV)void 0!==i&&(void 0!==i.strings?(i._$AI(t,i,e),e+=i.strings.length-2):i._$AI(t[e])),e++}}class X{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,e,i,s){this.type=2,this._$AH=W,this._$AN=void 0,this._$AA=t,this._$AB=e,this._$AM=i,this.options=s,this._$Cv=s?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode;const e=this._$AM;return void 0!==e&&11===t?.nodeType&&(t=e.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,e=this){t=Z(this,t,e),R(t)?t===W||null==t||""===t?(this._$AH!==W&&this._$AR(),this._$AH=W):t!==this._$AH&&t!==G&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):(t=>M(t)||"function"==typeof t?.[Symbol.iterator])(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==W&&R(this._$AH)?this._$AA.nextSibling.data=t:this.T(P.createTextNode(t)),this._$AH=t}$(t){const{values:e,_$litType$:i}=t,s="number"==typeof i?this._$AC(t):(void 0===i.el&&(i.el=K.createElement(F(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===s)this._$AH.p(e);else{const t=new Q(s,this),i=t.u(this.options);t.p(e),this.T(i),this._$AH=t}}_$AC(t){let e=B.get(t.strings);return void 0===e&&B.set(t.strings,e=new K(t)),e}k(t){M(this._$AH)||(this._$AH=[],this._$AR());const e=this._$AH;let i,s=0;for(const n of t)s===e.length?e.push(i=new X(this.O(T()),this.O(T()),this,this.options)):i=e[s],i._$AI(n),s++;s<e.length&&(this._$AR(i&&i._$AB.nextSibling,s),e.length=s)}_$AR(t=this._$AA.nextSibling,e){for(this._$AP?.(!1,!0,e);t!==this._$AB;){const e=w(t).nextSibling;w(t).remove(),t=e}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}}class Y{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,e,i,s,n){this.type=1,this._$AH=W,this._$AN=void 0,this.element=t,this.name=e,this._$AM=s,this.options=n,i.length>2||""!==i[0]||""!==i[1]?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=W}_$AI(t,e=this,i,s){const n=this.strings;let r=!1;if(void 0===n)t=Z(this,t,e,0),r=!R(t)||t!==this._$AH&&t!==G,r&&(this._$AH=t);else{const s=t;let o,a;for(t=n[0],o=0;o<n.length-1;o++)a=Z(this,s[i+o],e,o),a===G&&(a=this._$AH[o]),r||=!R(a)||a!==this._$AH[o],a===W?t=W:t!==W&&(t+=(a??"")+n[o+1]),this._$AH[o]=a}r&&!s&&this.j(t)}j(t){t===W?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}}class tt extends Y{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===W?void 0:t}}class et extends Y{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==W)}}class it extends Y{constructor(t,e,i,s,n){super(t,e,i,s,n),this.type=5}_$AI(t,e=this){if((t=Z(this,t,e,0)??W)===G)return;const i=this._$AH,s=t===W&&i!==W||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,n=t!==W&&(i===W||s);s&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}}class st{constructor(t,e,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=e,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){Z(this,t)}}const nt=A.litHtmlPolyfillSupport;nt?.(K,X),(A.litHtmlVersions??=[]).push("3.3.3");const rt=globalThis;let ot=class extends b{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const e=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=((t,e,i)=>{const s=i?.renderBefore??e;let n=s._$litPart$;if(void 0===n){const t=i?.renderBefore??null;s._$litPart$=n=new X(e.insertBefore(T(),t),t,void 0,i??{})}return n._$AI(t),n})(e,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return G}};ot._$litElement$=!0,ot.finalized=!0,rt.litElementHydrateSupport?.({LitElement:ot});const at=rt.litElementPolyfillSupport;at?.({LitElement:ot}),(rt.litElementVersions??=[]).push("4.2.2");const ct=2;class ht{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,e,i){this._$Ct=t,this._$AM=e,this._$Ci=i}_$AS(t,e){return this.update(t,e)}update(t,e){return this.render(...e)}}const lt=(t,e)=>{const i=t._$AN;if(void 0===i)return!1;for(const t of i)t._$AO?.(e,!1),lt(t,e);return!0},dt=t=>{let e,i;do{if(void 0===(e=t._$AM))break;i=e._$AN,i.delete(t),t=e}while(0===i?.size)},ut=t=>{for(let e;e=t._$AM;t=e){let i=e._$AN;if(void 0===i)e._$AN=i=new Set;else if(i.has(t))break;i.add(t),mt(e)}};function pt(t){void 0!==this._$AN?(dt(this),this._$AM=t,ut(this)):this._$AM=t}function gt(t,e=!1,i=0){const s=this._$AH,n=this._$AN;if(void 0!==n&&0!==n.size)if(e)if(Array.isArray(s))for(let t=i;t<s.length;t++)lt(s[t],!1),dt(s[t]);else null!=s&&(lt(s,!1),dt(s));else lt(this,t)}const mt=t=>{t.type==ct&&(t._$AP??=gt,t._$AQ??=pt)};class ft extends ht{constructor(){super(...arguments),this._$AN=void 0}_$AT(t,e,i){super._$AT(t,e,i),ut(this),this.isConnected=t._$AU}_$AO(t,e=!0){t!==this.isConnected&&(this.isConnected=t,t?this.reconnected?.():this.disconnected?.()),e&&(lt(this,t),dt(this))}setValue(t){if((t=>void 0===t.strings)(this._$Ct))this._$Ct._$AI(t,this);else{const e=[...this._$Ct._$AH];e[this._$Ci]=t,this._$Ct._$AI(e,this,0)}}disconnected(){}reconnected(){}}class _t{}const vt=new WeakMap,$t=(t=>(...e)=>({_$litDirective$:t,values:e}))(class extends ft{render(t){return W}update(t,[e]){const i=e!==this.G;return i&&this.rt(void 0),(i||this.lt!==this.ct)&&(this.G=e,this.ht=t.options?.host,this.rt(this.ct=t.element)),W}rt(t){if(void 0!==this.G)if(this.isConnected||(t=void 0),"function"==typeof this.G){const e=this.ht??globalThis;let i=vt.get(e);void 0===i&&(i=new WeakMap,vt.set(e,i)),void 0!==i.get(this.G)&&this.G.call(this.ht,void 0),i.set(this.G,t),void 0!==t&&this.G.call(this.ht,t)}else this.G.value=t}get lt(){return"function"==typeof this.G?vt.get(this.ht??globalThis)?.get(this.G):this.G?.value}disconnected(){this.lt===this.ct&&this.rt(void 0)}reconnected(){this.rt(this.ct)}});function yt(t,e){return t.callService("urmet","set_microphone",{muted:e})}class bt extends Error{constructor(t){super(t),this.name="UnsupportedCodecError"}}const At={createPeerConnection:t=>new RTCPeerConnection(t),getUserMedia:t=>navigator.mediaDevices.getUserMedia(t)};class wt{constructor(t,e,i){this.deps=t,this.onRemote=e,this.onDegraded=i,this.closed=!1}get hasMic(){return!!this.micTrack}async connect(t,e){this.callId=t??void 0;const i=this.deps.createPeerConnection({iceServers:[]});this.pc=i,i.addEventListener("track",t=>{const e=t.streams?.[0];e&&this.onRemote(e)}),i.addEventListener("connectionstatechange",()=>{"failed"===i.connectionState&&this.onDegraded("Connexion média perdue.")}),i.addTransceiver("video",{direction:"recvonly"}),this.audioSender=i.addTransceiver("audio",{direction:"sendrecv"}).sender;const s=await i.createOffer();await i.setLocalDescription(s),await this.waitForGathering(i);const n=i.localDescription;if(!n?.sdp)throw new Error("L'offre WebRTC est vide.");if(r=n.sdp,!/a=rtpmap:\d+ H264\//i.test(r)||!/a=rtpmap:\d+ PCMA\//i.test(r))throw new bt("Ce navigateur ne propose ni H264 ni PCMA: l'image et la voix du portier ne peuvent pas s'afficher ici.");var r;const o=await e({sdp:n.sdp,type:n.type});this.sessionId=o.session_id,o.call_id&&(this.callId=o.call_id),await i.setRemoteDescription({type:"answer",sdp:o.sdp})}async enableMic(){if(!this.pc||!this.audioSender||this.micTrack)return;const t=await this.deps.getUserMedia({audio:{echoCancellation:!0,noiseSuppression:!0,autoGainControl:!0},video:!1});this.micStream=t,this.micTrack=t.getAudioTracks()[0],await this.audioSender.replaceTrack(this.micTrack)}setMicEnabled(t){this.micTrack&&(this.micTrack.enabled=t)}close(){if(this.closed)return;this.closed=!0;for(const t of this.micStream?.getTracks()??[])t.stop();this.micStream=void 0,this.micTrack=void 0;const t=this.pc;if(t){for(const e of t.getReceivers())e.track?.stop();t.close()}this.pc=void 0,this.audioSender=void 0}waitForGathering(t){return"complete"===t.iceGatheringState?Promise.resolve():new Promise(e=>{let i;const s=()=>{clearTimeout(i),t.removeEventListener("icegatheringstatechange",n),e()},n=()=>{"complete"===t.iceGatheringState&&s()};i=setTimeout(s,2e3),t.addEventListener("icegatheringstatechange",n)})}}class St{constructor(t){this.onTick=t,this.seconds=0}ensure(){this.timer||(this.startedAt=Date.now(),this.seconds=0,this.timer=setInterval(()=>{this.seconds=Math.floor((Date.now()-(this.startedAt??Date.now()))/1e3),this.onTick()},1e3))}stop(){this.timer&&(clearInterval(this.timer),this.timer=void 0),this.seconds=0,this.startedAt=void 0}}const kt=["on_ring","always","never"],Ct="on_ring";function xt(t){const e=t?.calls??[],i=e.find(t=>"ringing"===t.state&&"incoming"===t.direction),s=e.find(t=>"streaming"===t.state),n=e.find(t=>"connecting"===t.state),r=s??n??i,o=r?(t?.sessions??[]).find(t=>t.call_id===r.id):void 0;return{registered:t?.registered??!1,doorphoneName:t?.doorphone?.name||"Portier",ringingCall:i,streamingCall:s,activeCall:r,micMuted:t?.mic_muted??!0,session:o,hasPicture:!!(o?.video&&o.video.width>0),degraded:"degraded"===o?.state}}function Et(t,e){if(e.config_entry_id)return e.config_entry_id;const i=e.device_id?t.devices?.[e.device_id]:void 0;return i?.primary_config_entry??i?.config_entries?.[0]??void 0}function Ut(t,e){if(t.entry_id)return{entryId:t.entry_id};const i=function(t){const e=new Set;for(const i of Object.values(t.entities??{})){if("urmet"!==i.platform)continue;const s=Et(t,i);s&&e.add(s)}return[...e]}(e);if(1===i.length)return{entryId:i[0]};if(i.length>1)return{error:"Plusieurs portiers configurés: précisez entry_id dans la configuration de la carte."};return Object.values(e.entities??{}).some(t=>"urmet"===t.platform)?{pending:!0}:{error:"Aucune entrée Portier Urmet n'est configurée."}}function Pt(t,e){return"negotiating"===t?"Connexion à la caméra du portier…":"waiting"===t?"En attente de l'image…":"live"!==t||e?void 0:"Le portier envoie le son sans image."}class Tt{constructor(t){this.host=t,this.vm=xt(void 0),this.linkState="idle",this.talking=!1,this.hasRemote=!1,this.connecting=!1,this.subscribing=!1,this.pendingCallId=null,this.autoStarted=!1,this.ringClock=new St(()=>this.host.requestUpdate()),t.addController(this)}get hasLink(){return!!this.link}hostConnected(){this.ensureStarted()}hostDisconnected(){this.teardown(),this.unsub&&(this.unsub().catch(t=>console.debug("urmet: unsubscribe failed",t)),this.unsub=void 0),this.ringClock.stop()}updateHass(t){this.hass=t,this.ensureStarted()}ensureStarted(){if(!this.host.isConnected||this.unsub||this.subscribing||!this.hass)return;const t=Ut(this.config??{},this.hass);if(this.resolveError=void 0,"pending"in t)return;if("error"in t)return void(this.resolveError=t.error);this.entryId=t.entryId,this.subscribing=!0;(function(t,e,i){return t.connection.subscribeMessage(t=>{t&&"state"===t.type&&i(t)},{type:"urmet/subscribe",entry_id:e})})(this.hass,this.entryId,t=>this.onState(t)).then(t=>{this.unsub=t}).catch(t=>{this.error="Impossible de se connecter à la passerelle du portier.",console.warn("urmet: subscribe failed",t),this.host.requestUpdate()}).finally(()=>{this.subscribing=!1})}answer(t){const e=this.hass;e&&(this.error=void 0,this.ignoredCallId=void 0,this.linkState="answering",this.pendingCallId=t,this.host.requestUpdate(),function(t,e){return t.callService("urmet","answer",e?{call_id:e}:{})}(e,t).catch(t=>this.fail("Impossible de répondre à l'appel.",t)))}look(){const t=this.hass;t&&(this.error=void 0,this.linkState="answering",this.pendingCallId=null,this.host.requestUpdate(),function(t){return t.callService("urmet","look",{want_video:!0})}(t).catch(t=>this.fail("Impossible de regarder le portier.",t)))}ignore(t){this.ignoredCallId=t,this.ringClock.stop(),this.host.requestUpdate()}hangUp(){const t=this.hass,e=this.vm.activeCall?.id;this.teardown(),this.host.requestUpdate(),t&&function(t,e){return t.callService("urmet","hang_up",e?{call_id:e}:{})}(t,e).catch(t=>console.warn("urmet: hang up failed",t))}async toggleTalk(){const t=this.hass,e=this.link;if(t&&e){try{this.talking?(e.setMicEnabled(!1),await yt(t,!0),this.talking=!1):(await e.enableMic(),e.setMicEnabled(!0),await yt(t,!1),this.talking=!0)}catch(t){this.error="Le micro n'a pas pu être activé.",console.warn("urmet: mic toggle failed",t)}this.host.requestUpdate()}}teardown(){const t=this.hass,e=this.entryId,i=this.sessionId;this.link?.close(),this.link=void 0,this.stream=void 0,this.hasRemote=!1,this.sessionId=void 0,this.pendingCallId=null,this.connecting=!1,this.talking=!1,this.linkState="idle",t&&e&&i&&function(t,e,i){return t.callWS({type:"urmet/webrtc/close",entry_id:e,session_id:i})}(t,e,i).catch(t=>console.debug("urmet: close session failed",t))}onState(t){this.state=t,this.vm=xt(t),this.react()}react(){const t=this.vm,e=this.config?.auto_start??Ct;t.ringingCall&&t.ringingCall.id!==this.ignoredCallId?this.ringClock.ensure():this.ringClock.stop(),this.advancePending(),"idle"===this.linkState?"always"!==e||t.activeCall||this.autoStarted||(this.autoStarted=!0,this.look()):"live"===this.linkState&&t.degraded&&(this.linkState="degraded"),this.host.requestUpdate()}advancePending(){if("answering"!==this.linkState)return;const t=this.state?.calls??[],e=this.pendingCallId?t.find(t=>t.id===this.pendingCallId):void 0;if(e&&("ended"===e.state||"error"===e.state))return this.error="error"===e.state?"L'appel n'a pas pu aboutir.":"L'appel s'est terminé.",void this.teardown();(this.pendingCallId?"streaming"===e?.state?e:void 0:this.vm.streamingCall)&&this.negotiate(this.pendingCallId)}async negotiate(t){const e=this.hass,i=this.entryId;if(!e||!i||this.connecting||this.link)return;this.connecting=!0,this.linkState="negotiating",this.error=void 0;const s=new wt(At,t=>this.onRemote(t),t=>this.onDegraded(t));this.link=s;try{await s.connect(t,s=>function(t,e,i,s){return t.callWS({type:"urmet/webrtc/offer",entry_id:e,sdp:i.sdp,call_id:s})}(e,i,s,t)),this.sessionId=s.sessionId,this.linkState=this.hasRemote?"live":"waiting"}catch(t){this.error=t instanceof bt?t.message:"La connexion vidéo a échoué.",console.warn("urmet: negotiate failed",t),this.teardown()}finally{this.connecting=!1,this.host.requestUpdate()}}onRemote(t){this.stream=t,this.hasRemote=!0,"negotiating"!==this.linkState&&"waiting"!==this.linkState||(this.linkState="live"),this.host.requestUpdate()}onDegraded(t){this.linkState="degraded",this.error=t,this.host.requestUpdate()}fail(t,e){this.error=t,console.warn("urmet:",t,e),this.teardown(),this.host.requestUpdate()}get ringSeconds(){return this.ringClock.seconds}}const Rt=r`
  :host {
    --urmet-fg: var(--primary-text-color, #212121);
    --urmet-muted: var(--secondary-text-color, #727272);
    --urmet-accent: var(--primary-color, #1e88e5);
    --urmet-danger: var(--error-color, #db4437);
    --urmet-ok: var(--success-color, #43a047);
    --urmet-line: var(--divider-color, #e0e0e0);
    display: block;
  }
  ha-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 12px;
    color: var(--urmet-fg);
  }
  .banner {
    background: var(--urmet-danger);
    color: #fff;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 0.9rem;
  }
  .ring {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--urmet-accent);
    color: #fff;
    border-radius: 10px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ring-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
  }
  .ring-title {
    flex: 1;
  }
  .ring-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #fff;
    animation: urmet-pulse 1s infinite;
  }
  @keyframes urmet-pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.3;
    }
  }
  .ring-preview,
  .stage-preview,
  .stage-video {
    width: 100%;
    aspect-ratio: 4 / 3;
    object-fit: cover;
    background: #000;
    border-radius: 8px;
    display: block;
  }
  .ring-actions {
    display: flex;
    gap: 8px;
  }
  .ring-note {
    margin: 0;
    font-size: 0.8rem;
    opacity: 0.9;
  }
  .stage {
    position: relative;
  }
  .stage-video[hidden] {
    display: none;
  }
  .stage-note {
    position: absolute;
    left: 8px;
    bottom: 8px;
    background: rgba(0, 0, 0, 0.6);
    color: #fff;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 0.85rem;
  }
  .stage-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    aspect-ratio: 4 / 3;
    background: var(--urmet-line);
    color: var(--urmet-muted);
    border-radius: 8px;
  }
  .stage-empty-icon {
    width: 28%;
    max-width: 88px;
    height: auto;
    opacity: 0.7;
  }
  .btn {
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    flex: 1;
    background: var(--urmet-line);
    color: var(--urmet-fg);
  }
  .btn:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .btn-answer {
    background: var(--urmet-ok);
    color: #fff;
  }
  .btn-ignore {
    background: rgba(255, 255, 255, 0.2);
    color: #fff;
  }
  .btn-hang {
    background: var(--urmet-danger);
    color: #fff;
  }
  .btn-talk-on {
    background: var(--urmet-accent);
    color: #fff;
  }
  .actions,
  .talk {
    display: flex;
    gap: 8px;
  }
  .talk-insecure p {
    margin: 0;
    font-size: 0.85rem;
    color: var(--urmet-muted);
  }
  .tech {
    border-top: 1px solid var(--urmet-line);
    padding-top: 8px;
  }
  .tech-title {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--urmet-muted);
    margin-bottom: 6px;
  }
  .tech-grid {
    display: grid;
    gap: 2px 12px;
    font-size: 0.8rem;
  }
  .tech-row {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  .tech-row span:first-child {
    color: var(--urmet-muted);
  }
`;function Mt(t,e){return q`<div class="tech-row"><span>${t}</span><span>${e}</span></div>`}const It=new Set(["type","entry_id","auto_start","preview_camera","show_tech","grid_options","layout_options","view_layout"]);class Ot extends ot{constructor(){super(...arguments),this._link=new Tt(this),this._videoRef=new _t}setConfig(t){for(const e of Object.keys(t))if(!It.has(e))throw new Error(`Clé de configuration inconnue: ${e}`);const e=t.auto_start??Ct;if(!kt.includes(e))throw new Error(`auto_start invalide: ${String(t.auto_start)}`);this._config={...t,auto_start:e,preview_camera:t.preview_camera,show_tech:t.show_tech??!0},this._link.config=this._config}set hass(t){const e=this._hass;this._hass=t;const i=function(t){for(const e of Object.values(t.entities??{}))if("urmet"===e.platform&&e.entity_id.startsWith("event.")&&e.entity_id.includes("doorbell"))return e.entity_id}(t);(function(t,e,i){return t===e||!(!t||!e)&&i.every(i=>t.states[i]===e.states[i])})(e,t,function(t,e){const i=[];return t?.preview_camera&&i.push(t.preview_camera),e&&i.push(e),i}(this._config,i))||this.requestUpdate(),this._link.updateHass(t)}get hass(){return this._hass}getCardSize(){return 8}getGridOptions(){return{rows:"auto",columns:12}}static getConfigElement(){return document.createElement("urmet-portier-card-editor")}static getStubConfig(){return{auto_start:Ct}}_cameraUrl(){const t=this._config?.preview_camera;if(!t)return;const e=this._hass?.states[t]?.attributes.access_token;return"string"==typeof e?`/api/camera_proxy_stream/${t}?token=${e}`:void 0}_assignStream(){const t=this._videoRef.value;if(!t)return;const e=this._link.stream??null;if(t.srcObject!==e&&(t.srcObject=e,t.muted=!0,e))try{const e=t.play?.();e&&e.then(()=>{t.muted=!1}).catch(t=>console.debug("urmet: play rejected",t))}catch(t){console.debug("urmet: play threw",t)}}updated(){this._assignStream()}render(){if(!this._config)return q``;const t=this._link;if(t.resolveError)return q`<ha-card><div class="banner" role="alert">${t.resolveError}</div></ha-card>`;const e=t.vm,i=this._cameraUrl(),s=e.ringingCall&&e.ringingCall.id!==t.ignoredCallId?e.ringingCall:void 0,n="undefined"!=typeof window&&window.isSecureContext,r="live"===t.linkState||"degraded"===t.linkState;return q`
      <ha-card>
        ${s?(o={name:e.doorphoneName,seconds:t.ringSeconds,cameraUrl:i,onAnswer:()=>t.answer(s.id),onIgnore:()=>t.ignore(s.id)},q`
    <div class="ring" role="alert" aria-live="assertive">
      <div class="ring-head">
        <span class="ring-dot"></span>
        <span class="ring-title">${o.name} sonne</span>
        <span class="ring-timer">${o.seconds}s</span>
      </div>
      ${o.cameraUrl?q`<img class="ring-preview" src=${o.cameraUrl} alt="Aperçu du portail" />`:W}
      <div class="ring-actions">
        <button class="btn btn-answer" @click=${o.onAnswer}>Décrocher</button>
        <button class="btn btn-ignore" @click=${o.onIgnore}>Ignorer</button>
      </div>
      <p class="ring-note">
        Ignorer laisse les combinés de la maison sonner. Décrocher prend l'appel et les combinés
        cessent de sonner.
      </p>
    </div>
  `):W}
        ${function(t){return q`
    <div class="stage">
      <video
        ${$t(t.videoRef)}
        class="stage-video"
        ?hidden=${!t.hasRemote}
        muted
        autoplay
        playsinline
      ></video>
      ${!t.hasRemote&&t.cameraUrl?q`<img class="stage-preview" src=${t.cameraUrl} alt="Aperçu du portail" />`:W}
      ${t.hasRemote||t.cameraUrl?W:q`<div class="stage-empty">
            <svg class="stage-empty-icon" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="7" y="2.5" width="10" height="19" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.3" />
              <circle cx="12" cy="8" r="2" fill="currentColor" />
              <rect x="10" y="13" width="4" height="1.5" rx="0.75" fill="currentColor" />
            </svg>
          </div>`}
      ${t.sentence?q`<div class="stage-note">${t.sentence}</div>`:W}
    </div>
  `}({videoRef:this._videoRef,hasRemote:t.hasRemote,cameraUrl:t.hasRemote?void 0:i,sentence:Pt(t.linkState,e.hasPicture)})}
        ${t.error?q`<div class="banner" role="alert">${t.error}</div>`:W}
        ${function(t){return t.secure?q`
    <div class="talk">
      <button
        class="btn ${t.talking?"btn-talk-on":""}"
        ?disabled=${!t.available}
        @click=${t.onToggle}
      >
        ${t.talking?"Couper le micro":"Parler"}
      </button>
    </div>
  `:q`
      <div class="talk talk-insecure">
        <p>
          Le micro demande une origine sécurisée: utilisez l'application mobile ou l'adresse HTTPS.
          L'écoute et l'image restent disponibles.
        </p>
      </div>
    `}({secure:n,talking:t.talking,available:r,onToggle:()=>{t.toggleTalk()}})}
        ${this._renderActions(t.hasLink,!!s)}
        ${this._config.show_tech?function(t){const e=t.vm.session,i=e?.video??null,s=e?.audio??null,n=t.vm.activeCall;return q`
    <div class="tech">
      <div class="tech-title">Technique</div>
      <div class="tech-grid">
        ${Mt("Lien",t.linkState)}
        ${Mt("Enregistré SIP",t.vm.registered?"oui":"non")}
        ${Mt("Micro",t.vm.micMuted?"coupé":"ouvert")}
        ${Mt("Appel",n?`${n.state} (${n.direction})`:"aucun")}
        ${Mt("Session",e?`${e.state} / ${e.connection}`:"aucune")}
        ${Mt("Image",i?`${i.width}x${i.height}`:"aucune")}
        ${Mt("Paquets vidéo",i?`${i.packets_sent} envoyés / ${i.packets_dropped} perdus`:"-")}
        ${Mt("Audio portier→nav",s?`${s.from_doorphone} → ${s.to_browser}`:"-")}
        ${Mt("Audio nav→portier",s?`${s.to_doorphone} (silence ${s.silence_sent})`:"-")}
        ${Mt("Audio perdu",s?`${s.dropped_from_doorphone} entrants / ${s.dropped_to_doorphone} sortants (${s.partial_from_doorphone} partiels)`:"-")}
        ${Mt("Callback audio",s?`${s.max_callback_ms.toFixed(1)} / ${s.budget_ms.toFixed(1)} ms`:"-")}
        ${t.sessionId?Mt("Session id",t.sessionId):W}
      </div>
    </div>
  `}({vm:e,linkState:t.linkState,sessionId:t.sessionId}):W}
      </ha-card>
    `;var o}_renderActions(t,e){if(t)return q`<div class="actions">
        <button class="btn btn-hang" @click=${()=>this._link.hangUp()}>Raccrocher</button>
      </div>`;if(e)return q``;const i="answering"===this._link.linkState||this._link.connecting;return q`<div class="actions">
      <button class="btn" ?disabled=${i} @click=${()=>this._link.look()}>Regarder</button>
    </div>`}}Ot.styles=Rt;class Ht extends ot{constructor(){super(...arguments),this._config={type:"custom:urmet-portier-card"}}setConfig(t){this._config={...t}}_emit(t){this._config={...this._config,...t},this.dispatchEvent(new CustomEvent("config-changed",{detail:{config:this._config},bubbles:!0,composed:!0}))}render(){const t=this._config;return q`
      <div class="form">
        <label>
          entry_id (optionnel quand un seul portier existe)
          <input
            .value=${t.entry_id??""}
            @change=${t=>this._emit({entry_id:t.target.value||void 0})}
          />
        </label>
        <label>
          auto_start
          <select
            @change=${t=>this._emit({auto_start:t.target.value})}
          >
            ${kt.map(e=>q`<option value=${e} ?selected=${(t.auto_start??Ct)===e}>
                  ${e}
                </option>`)}
          </select>
        </label>
        <label>
          preview_camera
          <input
            placeholder="camera.your_door_camera (optional)"
            .value=${t.preview_camera??""}
            @change=${t=>this._emit({preview_camera:t.target.value})}
          />
        </label>
        <label class="row">
          <input
            type="checkbox"
            .checked=${t.show_tech??!0}
            @change=${t=>this._emit({show_tech:t.target.checked})}
          />
          Panneau technique
        </label>
      </div>
    `}}Ht.properties={_config:{state:!0}},Ht.styles=r`
    .form {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 8px 0;
    }
    label {
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 0.85rem;
      color: var(--secondary-text-color, #727272);
    }
    label.row {
      flex-direction: row;
      align-items: center;
      gap: 8px;
    }
    input,
    select {
      font: inherit;
      padding: 6px 8px;
    }
  `;const Nt="urmet-portier-card",Dt="urmet-portier-card-editor";customElements.get(Nt)||customElements.define(Nt,Ot),customElements.get(Dt)||customElements.define(Dt,Ht);const Lt=window;Lt.customCards=Lt.customCards??[],Lt.customCards.push({type:Nt,name:"Portier Urmet",description:"Answer the Urmet doorphone, watch the gate and open the door or gate from Home Assistant.",preview:!0,documentationURL:"https://github.com/fabienvauchelles/urmet-ha"});
