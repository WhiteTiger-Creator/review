use std::{collections::{BTreeMap,BTreeSet},env,fs,path::Path};
fn rows(p:&Path)->Result<Vec<Vec<String>>,String>{let s=fs::read_to_string(p).map_err(|e|e.to_string())?;Ok(s.lines().skip(1).filter(|x|!x.trim().is_empty()).map(|x|x.split(',').map(|v|v.trim().to_string()).collect()).collect())}
fn cls(s:&str)->Result<usize,String>{match s{"DE"=>Ok(0),"GB"=>Ok(1),"US"=>Ok(2),_=>Err("class".into())}}
fn run()->Result<(),String>{
 let data=env::var("DATA_PATH").unwrap_or("/app/data".into());let out=env::var("OUTPUT_PATH").unwrap_or("/app/output".into());let b=Path::new(&data);
 let mut artists=BTreeSet::new();for r in rows(&b.join("artists.csv"))?{if r.len()!=2||!artists.insert(r[0].clone()){return Err("artist".into())}}
 let mut tags=BTreeSet::new();for r in rows(&b.join("tags.csv"))?{if r.len()!=1||!tags.insert(r[0].clone()){return Err("tag".into())}}
 let mut at:BTreeMap<String,BTreeSet<String>>=BTreeMap::new();let mut ep=BTreeSet::new();for r in rows(&b.join("artist_tags.csv"))?{if r.len()!=2||!artists.contains(&r[0])||!tags.contains(&r[1])||!ep.insert((r[0].clone(),r[1].clone())){return Err("edge".into())}at.entry(r[0].clone()).or_default().insert(r[1].clone());}
 let mut train=BTreeMap::new();let mut nc=[0usize;3];for r in rows(&b.join("train_labels.csv"))?{if r.len()!=2||!artists.contains(&r[0])||train.contains_key(&r[0]){return Err("label".into())}let y=cls(&r[1])?;nc[y]+=1;train.insert(r[0].clone(),y);}if nc.iter().any(|&x|x==0){return Err("classes".into())}
 let mut q=BTreeSet::new();for r in rows(&b.join("queries.csv"))?{if r.len()!=1||!artists.contains(&r[0])||train.contains_key(&r[0])||!q.insert(r[0].clone())||at.get(&r[0]).map_or(true,|x|x.is_empty()){return Err("query".into())}}
 let mut count:Vec<BTreeMap<String,usize>>=vec![BTreeMap::new(),BTreeMap::new(),BTreeMap::new()];let mut total=[0usize;3];for(a,&y)in &train{for t in at.get(a).into_iter().flatten(){*count[y].entry(t.clone()).or_default()+=1;total[y]+=1}}
 fs::create_dir_all(&out).map_err(|e|e.to_string())?;let names=["DE","GB","US"];let mut s="artist_id,prob_DE,prob_GB,prob_US,predicted_country\n".to_string();
 for a in q{let mut z=[0.0f64;3];for k in 0..3{z[k]=(nc[k] as f64/train.len() as f64).ln();for t in at.get(&a).into_iter().flatten(){z[k]+=((*count[k].get(t).unwrap_or(&0)+1)as f64/(total[k]+tags.len())as f64).ln()}}let m=z[0].max(z[1]).max(z[2]);let mut p=[(z[0]-m).exp(),(z[1]-m).exp(),(z[2]-m).exp()];let d=p.iter().sum::<f64>();for x in &mut p{*x/=d}let mut best=0;for k in 1..3{if p[k]>p[best]{best=k}}s.push_str(&format!("{},{:.12},{:.12},{:.12},{}\n",a,p[0],p[1],p[2],names[best]));}
 fs::write(Path::new(&out).join("predictions.csv"),s).map_err(|e|e.to_string())?;Ok(())}
fn main(){if let Err(e)=run(){eprintln!("{}",e);std::process::exit(1)}}
