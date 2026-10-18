export function formatCurrency(value:number|null|undefined,currency?:string):string{
  if(value==null || !Number.isFinite(value))return '—'
  if(!currency)return new Intl.NumberFormat('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).format(value)
  return new Intl.NumberFormat('en-US',{style:'currency',currency}).format(value)
}
export function formatPct(value:number|null|undefined):string{
  if(value==null || !Number.isFinite(value))return '—'
  return new Intl.NumberFormat('en-US',{style:'percent',minimumFractionDigits:1}).format(value/100)
}

export function formatCompact(value:unknown):string{
  const numeric=Number(value)
  return Number.isFinite(numeric)?new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1}).format(numeric):'—'
}
