import { useState, useEffect } from 'react';

export function useDataset() {
  const [datasetId, setDatasetIdState] = useState<string | null>(null);

  useEffect(() => {
    const id = localStorage.getItem('datasetId');
    if (id) setDatasetIdState(id);
  }, []);

  const setDatasetId = (id: string | null) => {
    if (id) {
      localStorage.setItem('datasetId', id);
    } else {
      localStorage.removeItem('datasetId');
    }
    setDatasetIdState(id);
  };

  return { datasetId, setDatasetId };
}
