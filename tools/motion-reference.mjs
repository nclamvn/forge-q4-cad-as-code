// Fixed, local reference compiler. Reads data; never evaluates user code.
import fs from 'node:fs';
import {MOTIONS,trajectory} from '../web/motion-engine.js';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
if(!MOTIONS.some(m=>m.id===input.motion))throw new Error('Unknown motion');
const samples=trajectory(input.spec,input.motion,input.amplitude,input.speed,120);
process.stdout.write(JSON.stringify({motion:input.motion,duration:samples.at(-1).seconds,
  samples:samples.map(s=>({seconds:s.seconds,commands:s.legs.flatMap(l=>l.offset_from_cad_rad)}))}));
