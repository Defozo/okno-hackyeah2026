export interface Source {label:string;url?:string|null;checked_at?:string|null;valid_from?:string|null;valid_to?:string|null;status:'current'|'stale'|'unknown'}
export interface CalendarRule {weekdays:number[];dates?:string[];excluded_dates?:string[];valid_from?:string|null;valid_to?:string|null}
export interface Availability extends CalendarRule {start:string|null;end:string|null;start_fold?:number|null;end_fold?:number|null}
export interface Activity extends CalendarRule {id:string;label:string;kind:'work'|'course'|'obligation';location:string;start:string|null;duration_minutes:number;paid_minutes:number;negotiable:boolean;start_min:string|null;start_max:string|null;step_minutes:number;agreement_id:string|null;required:boolean;offer_group:string|null;requires_activity_ids:string[];cost_grosze:number|null;cost_frequency:'once'|'occurrence';source:Source;start_fold?:number|null}
export interface CareHandoff {at:string;at_fold?:number|null;by_resource_id:string;leg_id:string|null;confirmed:boolean;valid_to:string|null;source:Source}
export interface CareArrangement {id:string;resource_ids:string[];handoffs:CareHandoff[];unavailable?:CalendarRule[]}
export interface CareNeed extends CalendarRule {id:string;dependent_id:string;label:string;care_type:string;start:string|null;end:string|null;allow_self_care:boolean;resource_ids:string[];visit_order:number;arrangements:CareArrangement[]}
export interface CareResource {id:string;label:string;location:string;kind:'facility'|'caregiver'|'service';capacity:number;dependent_ids:string[];care_types:string[];availability:Availability[];busy:Availability[];confirmed:boolean;negotiable:boolean;confirmation_valid_to:string|null;daily_cost_grosze:number|null;hourly_cost_grosze:number|null;one_time_cost_grosze:number|null;source:Source}
export interface TravelBand extends CalendarRule {start:string;end:string;minutes:number|null;cost_grosze:number|null}
export interface TravelLeg {id:string;origin:string;destination:string;mode:'manual'|'walk'|'transit'|'bike'|'car';bands:TravelBand[];access_minutes:number;handoff_minutes:number;buffer_minutes:number;source:Source}
export interface Scenario {schema_version:1;title:string;version:number;data_mode:'synthetic'|'personal';start_date:string;end_date:string;timezone:'Europe/Warsaw';home_location:string;location_coordinates:Record<string,{lat:number;lon:number}>;self_care_capacity:number;activities:Activity[];care_needs:CareNeed[];care_resources:CareResource[];travel_legs:TravelLeg[];budget_grosze:number|null;minimum_paid_minutes:number;minimum_rest_minutes:number;preferred_extra_buffer_minutes:number;objective_order:string[];notes:string;forbidden_proposals:AnyRecord[]}
export type AnyRecord = Record<string,any>;
export interface SavedPlan {id:string;version:number;scenario:Scenario;result:AnyRecord|null;selected_alternative_id?:string;decisions:AnyRecord[];outcomes:AnyRecord[];trial:AnyRecord|null;status:string;versions:AnyRecord[];updated_at:string;impact?:AnyRecord;rejected_alternatives?:AnyRecord[]}
export const weekdays=['Pon','Wt','Śr','Czw','Pt','Sob','Nd'];
export const uid=(prefix:string)=>`${prefix}-${crypto.randomUUID().slice(0,8)}`;
export const source=():Source=>({label:'deklaracja użytkowniczki',status:'current'});
export function blankScenario():Scenario {const start = new Date();start.setDate(start.getDate()+((8-start.getDay())%7||7));const end=new Date(start);end.setDate(end.getDate()+27);return {schema_version:1,title:'Mój plan powrotu',version:1,data_mode:'personal',start_date:start.toISOString().slice(0,10),end_date:end.toISOString().slice(0,10),timezone:'Europe/Warsaw',home_location:'dom',location_coordinates:{},self_care_capacity:1,activities:[],care_needs:[],care_resources:[],travel_legs:[],budget_grosze:null,minimum_paid_minutes:0,minimum_rest_minutes:660,preferred_extra_buffer_minutes:15,objective_order:['changed_agreements','shift_minutes','cost_grosze'],notes:'',forbidden_proposals:[]};}
export function newActivity():Activity {const id=uid('praca');return {id,label:'Moja oferta',kind:'work',location:'praca',start:null,duration_minutes:480,paid_minutes:480,weekdays:[0,1,2,3,4],negotiable:false,start_min:null,start_max:null,step_minutes:15,agreement_id:id,required:true,offer_group:null,requires_activity_ids:[],cost_grosze:0,cost_frequency:'once',source:source()};}
export function newResource():CareResource {const id=uid('opieka');return {id,label:'Miejsce opieki',location:id,kind:'facility',capacity:1,dependent_ids:[],care_types:['child'],availability:[{start:null,end:null,weekdays:[0,1,2,3,4]}],busy:[],confirmed:false,negotiable:true,confirmation_valid_to:null,daily_cost_grosze:null,hourly_cost_grosze:0,one_time_cost_grosze:0,source:source()};}
export function normalizeScenario(raw:AnyRecord):Scenario {const blank=blankScenario();return {...blank,...raw,location_coordinates:raw.location_coordinates||{},forbidden_proposals:raw.forbidden_proposals||[],activities:(raw.activities||[]).map((a:AnyRecord)=>({...newActivity(),...a,source:{...source(),...a.source}})),care_needs:(raw.care_needs||[]).map((n:AnyRecord)=>({weekdays:[0,1,2,3,4],resource_ids:[],arrangements:[],allow_self_care:true,visit_order:0,...n})),care_resources:(raw.care_resources||[]).map((r:AnyRecord)=>({...newResource(),...r,source:{...source(),...r.source}})),travel_legs:(raw.travel_legs||[]).map((t:AnyRecord)=>({access_minutes:0,handoff_minutes:0,buffer_minutes:0,...t,source:{...source(),...t.source}}))};}

/** Localize technical labels only when opening a new example. Saved and own
 * plans continue through normalizeScenario and keep their original labels. */
export function normalizeExample(raw:AnyRecord):Scenario {
 const scenario=normalizeScenario(structuredClone(raw));
 const uniqueLabels=(values:string[],translate:(value:string)=>string)=>{
  const originals=[...new Set(values)];
  const key=(value:string)=>value.trim().toLocaleLowerCase('pl');
  // Reserve existing human labels first: home -> dom must not merge two
  // distinct places when the example already contains a place called dom.
  const used=new Set(originals.filter(value=>translate(value)===value).map(key));
  const labels=new Map<string,string>();
  for(const original of originals){
   const base=translate(original);
   let label=base;
   if(base!==original){let suffix=2;while(used.has(key(label)))label=`${base} (${suffix++})`;}
   used.add(key(label));labels.set(original,label);
  }
  return labels;
 };
 const places=uniqueLabels([scenario.home_location,...scenario.activities.map(a=>a.location),
  ...scenario.care_resources.map(r=>r.location),...scenario.travel_legs.flatMap(t=>[t.origin,t.destination]),
  ...Object.keys(scenario.location_coordinates)],value=>{
   if(value==='home')return 'dom';
   if(value==='work')return 'praca';
   if(value==='care')return 'miejsce opieki';
   const numbered=/^care-(\d+)$/.exec(value);
   return numbered?`miejsce opieki ${numbered[1]}`:value;
  });
 const dependents=uniqueLabels([...scenario.care_needs.map(n=>n.dependent_id),
  ...scenario.care_resources.flatMap(r=>r.dependent_ids)],value=>{
   const numbered=/^(child|adult|dependent)-(\d+)$/.exec(value);
   if(!numbered)return value;
   const kind=numbered[1]==='child'?'dziecko':numbered[1]==='adult'?'osoba dorosła':'podopieczny';
   return `${kind} ${numbered[2]}`;
  });
 const place=(value:string)=>places.get(value)??value;
 const dependent=(value:string)=>dependents.get(value)??value;
 return {...scenario,home_location:place(scenario.home_location),
  activities:scenario.activities.map(a=>({...a,location:place(a.location)})),
  care_needs:scenario.care_needs.map(n=>({...n,dependent_id:dependent(n.dependent_id)})),
  care_resources:scenario.care_resources.map(r=>({...r,location:place(r.location),dependent_ids:r.dependent_ids.map(dependent)})),
  travel_legs:scenario.travel_legs.map(t=>({...t,origin:place(t.origin),destination:place(t.destination)})),
  location_coordinates:Object.fromEntries(Object.entries(scenario.location_coordinates).map(([label,coordinates])=>[place(label),coordinates]))};
}
