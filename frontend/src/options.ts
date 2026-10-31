export interface Option {
  value: string;
  label: string;
}

const NOT_SURE: Option = { value: "unknown", label: "Not sure" };

export const FLOOD_ZONES: Option[] = [
  { value: "A", label: "A: high-risk area" },
  { value: "V", label: "V: coastal high-risk area" },
  { value: "X", label: "X: moderate or low risk" },
  { value: "D", label: "D: undetermined risk" },
  NOT_SURE,
];

export const FLOORS: Option[] = [
  { value: "1", label: "One floor" },
  { value: "2", label: "Two floors" },
  { value: "3+", label: "Three or more floors" },
  { value: "split_level", label: "Split level" },
  { value: "mobile_home", label: "Mobile home" },
  { value: "townhouse_3+", label: "Townhouse, three or more floors" },
  NOT_SURE,
];

export const FOUNDATIONS: Option[] = [
  { value: "slab", label: "Slab on the ground" },
  { value: "basement", label: "Basement" },
  { value: "crawlspace", label: "Crawlspace" },
  { value: "elevated_open", label: "Raised, open (posts or piers)" },
  { value: "elevated_enclosed_piles", label: "Raised, enclosed (piles)" },
  { value: "elevated_enclosed_walls", label: "Raised, enclosed (walls)" },
  NOT_SURE,
];

export const BASEMENTS: Option[] = [
  { value: "none", label: "No basement" },
  { value: "finished_basement", label: "Finished basement" },
  { value: "unfinished_basement", label: "Unfinished basement" },
  { value: "crawlspace", label: "Crawlspace" },
  { value: "subgrade_crawlspace", label: "Below-ground crawlspace" },
  NOT_SURE,
];

export function labelFor(options: Option[], value: string): string {
  return options.find((o) => o.value === value)?.label ?? value;
}
