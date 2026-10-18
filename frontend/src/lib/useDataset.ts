'use client'
import {useCallback,useSyncExternalStore} from 'react'
const KEY='finops.datasetId'
const EVENT='finops:dataset'
function subscribe(listener:()=>void){
  window.addEventListener(EVENT,listener);window.addEventListener('storage',listener)
  return ()=>{window.removeEventListener(EVENT,listener);window.removeEventListener('storage',listener)}
}
export function getSelectedDatasetId(){return typeof window==='undefined'?null:localStorage.getItem(KEY)}
export function useDataset(){
  const datasetId=useSyncExternalStore(subscribe,getSelectedDatasetId,()=>null)
  const setDatasetId=useCallback((id:string|null)=>{
    if(id)localStorage.setItem(KEY,id);else localStorage.removeItem(KEY)
    window.dispatchEvent(new Event(EVENT))
  },[])
  return {datasetId,setDatasetId}
}
export function clearDataset(){
  localStorage.removeItem(KEY);localStorage.removeItem('datasetId')
  window.dispatchEvent(new Event(EVENT))
}
