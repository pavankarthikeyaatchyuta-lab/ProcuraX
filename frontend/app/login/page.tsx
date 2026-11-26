'use client';
import {useRouter} from 'next/navigation';
import {useEffect} from 'react';
import {ShieldCheck,Check} from 'lucide-react';
import {useWorkspace} from '../../components/workspace';
import {Form} from '../../components/ui';

function ProcuraXLogo() {
  return (
    <svg width="34" height="34" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="login-c1" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
        <linearGradient id="login-c2" x1="0" y1="20" x2="20" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1d4ed8" />
          <stop offset="100%" stopColor="#0f172a" />
        </linearGradient>
        <filter id="login-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      <path d="M20 3 L36 12 L36 28 L20 37 L4 28 L4 12 Z" fill="url(#login-c2)" />
      <path d="M20 3 L36 12 L20 21 L4 12 Z" fill="#60a5fa" opacity="0.85" />
      <path d="M20 21 L36 12 L36 28 L20 37 Z" fill="url(#login-c1)" />
      <path d="M20 21 L4 12 L4 28 L20 37 Z" fill="#1e40af" />
      <path d="M20 9 L31 15 L20 21 L9 15 Z" fill="#93c5fd" opacity="0.9" />
      <path d="M16 16 L23 16 C25 16 26 17 26 19 C26 21 25 22 23 22 L19 22 L19 27 L16 27 Z M19 18.5 L19 20 L22.5 20 C23 20 23.5 19.7 23.5 19.2 C23.5 18.8 23 18.5 22.5 18.5 Z" fill="#ffffff" filter="url(#login-glow)" />
    </svg>
  );
}

export default function Login(){
  const {me,profile}=useWorkspace(),router=useRouter();
  useEffect(()=>{if(me)router.replace('/overview')},[me,router]);
  return (
    <div className="login-page">
      <section className="login-intro">
        <div className="brand" style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
          <ProcuraXLogo />
          <div>
            <div style={{fontSize: '22px', fontWeight: 800, letterSpacing: '-0.02em', color: '#ffffff', lineHeight: 1.1}}>ProcuraX</div>
            <div style={{fontSize: '11px', color: '#94a3b8', fontWeight: 500}}>AI Procurement Intelligence for MSMEs</div>
          </div>
        </div>
        <div>
          <span className="login-label">PROCUREMENT, MADE INTELLIGENT</span>
          <h1>Know what to buy.<br/>When to buy.<br/><em>How much to buy and where.</em></h1>
          <p>Connect supplier invoices, real-time stock, purchase prices and local market demand — all in one AI-powered workspace.</p>
          <div className="login-features">
            <span><Check/>Verified invoice extraction & price anomaly detection</span>
            <span><Check/>Cash-flow-aware purchasing & stock replenishment</span>
            <span><Check/>Local customer demand & profit leak protection</span>
          </div>
        </div>
        <small>Purpose-built for Indian grocery, retail, pharmacy and wholesale MSMEs.</small>
      </section>
      <section className="login-right">
        <div className="login-box">
          <span className="secure-label"><ShieldCheck size={16}/>Secure workspace</span>
          <h2>Welcome to ProcuraX</h2>
          <p>Sign in to manage your procurement intelligence.</p>
          <Form
            button="Sign in"
            fields={[
              {key:'email',label:'Email address',type:'email',required:true},
              {key:'password',label:'Password',type:'password',required:true}
            ]}
            onSubmit={async values=>{
              const response=await fetch('/api/v1/auth/login',{
                method:'POST',
                headers:{'Content-Type':'application/json'},
                body:JSON.stringify(values)
              });
              const body=await response.json();
              if(!response.ok)throw new Error(body.detail);
              await profile();
              router.push('/overview');
            }}
          />
          <div className="login-footnote">
            Demo Credentials: <strong>owner@vyaya.local</strong> / <strong>password123</strong><br/>
            Your business records stay isolated and securely stored in your local workspace.
          </div>
        </div>
      </section>
    </div>
  );
}
