const https = require('https');
const nodemailer = require('nodemailer');

// ── YOUR PROFILE ──
const PROFILE = {
  name: 'Venkatesan P',
  keywords: [
    'capex', 'capital expenditure', 'project manager', 'program manager',
    'pmo', 'governance', 'cost control', 'budget', 'variance',
    'cpm', 'pert', 'scheduling', 'ms project', 'power bi',
    'sap', 'sap mm', 'vendor', 'procurement', 'risk management',
    'mechanical', 'manufacturing', 'plant', 'infrastructure',
    'epc', 'shutdown', 'wbs', 'milestone', 'capex management',
    'project engineer', 'program governance', 'project planning',
    'contract management', 'stakeholder', 'commissioning'
  ]
};

// ── SEARCH QUERIES ──
const SEARCH_QUERIES = [
  { label: 'CAPEX PM India Core',         query: 'Project Manager CAPEX manufacturing India',         country: 'in' },
  { label: 'Program Manager PMO India',   query: 'Program Manager PMO capital projects India',        country: 'in' },
  { label: 'Aerospace Defence PM',        query: 'Project Manager aerospace defence India',           country: 'in' },
  { label: 'Tech Automation PM',          query: 'Project Manager industrial automation India',       country: 'in' },
  { label: 'Clean Energy PM',             query: 'Project Manager energy infrastructure India',       country: 'in' },
  { label: 'Power BI SAP Roles',          query: 'Project Manager Power BI SAP manufacturing India',  country: 'in' },
  { label: 'EPC Project Engineer India',  query: 'Project Engineer EPC plant infrastructure India',   country: 'in' },
  { label: 'Gulf CAPEX PM',               query: 'CAPEX Project Manager manufacturing UAE',           country: 'ae' },
];

// ── TARGET COMPANIES ──
const TARGET_COMPANIES = [
  'siemens','honeywell','abb','ge ','boeing','rtx','raytheon',
  'rolls-royce','bosch','schneider','caterpillar','collins','safran',
  'tata','mahindra','ltts','l&t','hal ','drdo','bhel','ntpc',
  'isro','ola electric','ather','amazon','rockwell','godrej','kirloskar','bel '
];

// ── HELPERS ──
function matchScore(title = '', desc = '') {
  const text = (title + ' ' + desc).toLowerCase();
  let hits = 0;
  PROFILE.keywords.forEach(kw => { if (text.includes(kw)) hits++; });
  return Math.min(97, Math.max(20, Math.round((hits / PROFILE.keywords.length) * 100)));
}

function isTargetCompany(employer = '') {
  const e = employer.toLowerCase();
  return TARGET_COMPANIES.some(c => e.includes(c.trim()));
}

function detectSource(url = '') {
  const u = url.toLowerCase();
  if (u.includes('linkedin'))   return 'LinkedIn';
  if (u.includes('naukri'))     return 'Naukri';
  if (u.includes('indeed'))     return 'Indeed';
  if (u.includes('glassdoor'))  return 'Glassdoor';
  if (u.includes('/careers') || u.includes('jobs.')) return 'Company Direct';
  return 'Job Board';
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── FETCH JOBS ──
function fetchJobs(query, country) {
  return new Promise((resolve) => {
    const params = new URLSearchParams({
      query,
      page: '1',
      num_pages: '2',
      country: country || 'in',
      language: 'en',
      date_posted: 'week',
      employment_types: 'FULLTIME'
    });

    const options = {
      hostname: 'jsearch.p.rapidapi.com',
      path: `/search?${params.toString()}`,
      method: 'GET',
      headers: {
        'x-rapidapi-host': 'jsearch.p.rapidapi.com',
        'x-rapidapi-key': process.env.RAPIDAPI_KEY
      }
    };

    const req = https.request(options, res => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(body).data || []); }
        catch (e) { console.error('Parse error:', e.message); resolve([]); }
      });
    });

    req.on('error', e => { console.error('Request error:', e.message); resolve([]); });
    req.setTimeout(15000, () => { req.destroy(); resolve([]); });
    req.end();
  });
}

// ── BUILD EMAIL ──
function buildEmail(jobs, date) {
  const high   = jobs.filter(j => j.score >= 80);
  const medium = jobs.filter(j => j.score >= 60 && j.score < 80);
  const low    = jobs.filter(j => j.score >= 40 && j.score < 60);
  const target = jobs.filter(j => j.isTarget && j.score < 40);

  const card = j => `
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px">
    <tr><td style="background:#0c0f18;border:1px solid #1e2438;border-left:3px solid ${j.score>=80?'#00c48c':j.score>=60?'#f0a30a':'#3d7fff'};border-radius:10px;padding:14px 16px">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-size:15px;font-weight:700;color:#e2e8f0;padding-bottom:4px">${j.title}</td>
          <td align="right" style="white-space:nowrap">
            <span style="background:${j.score>=80?'rgba(0,196,140,0.15)':j.score>=60?'rgba(240,163,10,0.12)':'rgba(61,127,255,0.12)'};color:${j.score>=80?'#00c48c':j.score>=60?'#f0a30a':'#93c5fd'};padding:3px 10px;border-radius:99px;font-size:12px;font-weight:700">⚡ ${j.score}%</span>
          </td>
        </tr>
        <tr><td colspan="2" style="font-size:13px;color:${j.isTarget?'#f0a30a':'#7a859e'};padding-bottom:6px">${j.isTarget?'⭐ ':''}${j.company}</td></tr>
        <tr><td colspan="2" style="font-size:12px;color:#3a4260;padding-bottom:10px">📍 ${j.location} &nbsp;·&nbsp; 🗓 ${j.date} &nbsp;·&nbsp; 🔗 ${j.source}</td></tr>
        <tr><td colspan="2" style="font-size:12px;color:#5a6278;line-height:1.6;padding-bottom:12px">${j.desc}</td></tr>
        <tr><td colspan="2">
          <a href="${j.url}" style="display:inline-block;background:#f0a30a;color:#000;padding:6px 16px;border-radius:7px;font-size:12px;font-weight:700;text-decoration:none">Apply Now →</a>
        </td></tr>
      </table>
    </td></tr>
    </table>`;

  const section = (label, color, list) => list.length === 0 ? '' : `
    <tr><td style="padding:18px 20px 10px">
      <div style="color:${color};font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid ${color}44;padding-bottom:8px">${label} — ${list.length} job${list.length>1?'s':''}</div>
    </td></tr>
    <tr><td style="padding:0 20px">${list.map(card).join('')}</td></tr>`;

  return `<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#07090e;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#07090e;padding:24px 16px">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%">

  <tr><td style="background:#0c0f18;border:1px solid #1e2438;border-bottom:3px solid #f0a30a;border-radius:14px 14px 0 0;padding:22px 20px">
    <div style="font-size:11px;color:#3a4260;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px">Daily Job Alert · ${date}</div>
    <div style="font-size:22px;font-weight:800;color:#e2e8f0;margin-bottom:4px">🎯 ${jobs.length} Matching Jobs Found</div>
    <div style="font-size:13px;color:#7a859e">Venkatesan P · CAPEX / Project Management · India + Gulf</div>
  </td></tr>

  <tr><td style="background:#111520;border-left:1px solid #1e2438;border-right:1px solid #1e2438;padding:14px 20px">
    <table width="100%" cellpadding="4" cellspacing="0">
    <tr>
      <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid #1e2438;padding:12px 8px">
        <div style="font-size:22px;font-weight:800;color:#f0a30a">${jobs.length}</div>
        <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">Total</div>
      </td>
      <td width="8"></td>
      <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid #1e2438;padding:12px 8px">
        <div style="font-size:22px;font-weight:800;color:#00c48c">${high.length}</div>
        <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">80%+ Match</div>
      </td>
      <td width="8"></td>
      <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid #1e2438;padding:12px 8px">
        <div style="font-size:22px;font-weight:800;color:#f0a30a">${medium.length}</div>
        <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">60–79%</div>
      </td>
      <td width="8"></td>
      <td align="center" style="background:#0c0f18;border-radius:9px;border:1px solid rgba(155,114,255,0.4);padding:12px 8px">
        <div style="font-size:22px;font-weight:800;color:#9b72ff">${jobs.filter(j=>j.isTarget).length}</div>
        <div style="font-size:10px;color:#3a4260;text-transform:uppercase;margin-top:3px">⭐ Target Cos</div>
      </td>
    </tr>
    </table>
  </td></tr>

  <tr><td style="background:#0c0f18;border:1px solid #1e2438;border-top:none;border-radius:0 0 14px 14px">
    <table width="100%" cellpadding="0" cellspacing="0">
      ${section('🔥 Excellent Match — 80%+',  '#00c48c', high)}
      ${section('✅ Good Match — 60–79%',      '#f0a30a', medium)}
      ${section('📋 Partial Match — 40–59%',   '#3d7fff', low)}
      ${section('⭐ Target Companies',          '#9b72ff', target)}
    </table>
  </td></tr>

  <tr><td style="padding:12px 0;text-align:center">
    <div style="font-size:11px;color:#3a4260">JobAlert Bot · GitHub Actions · Runs 8 AM & 1 PM IST weekdays</div>
  </td></tr>

</table>
</td></tr>
</table>
</body></html>`;
}

// ── SEND EMAIL ──
async function sendEmail(html, count, date) {
  const transporter = nodemailer.createTransporter({
    service: 'gmail',
    auth: {
      user: process.env.FROM_EMAIL,
      pass: process.env.GMAIL_APP_PASSWORD
    }
  });

  const info = await transporter.sendMail({
    from: `"JobAlert Bot 🤖" <${process.env.FROM_EMAIL}>`,
    to: process.env.TO_EMAIL,
    subject: `🎯 ${count} Jobs Found — ${date} | JobAlert Bot`,
    html
  });

  console.log(`✅ Email sent! ID: ${info.messageId}`);
}

// ── MAIN ──
async function main() {
  console.log('\n🚀 JobAlert Bot Starting...');

  if (!process.env.RAPIDAPI_KEY) {
    console.error('❌ RAPIDAPI_KEY secret not set!');
    process.exit(1);
  }

  const date = new Date().toLocaleDateString('en-IN', {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
  });

  // Fetch all queries
  const seen = new Map();
  for (const q of SEARCH_QUERIES) {
    console.log(`🔍 ${q.label}...`);
    const jobs = await fetchJobs(q.query, q.country);
    console.log(`   → ${jobs.length} results`);
    jobs.forEach(j => { if (!seen.has(j.job_id)) seen.set(j.job_id, j); });
    await sleep(1500);
  }

  console.log(`\n📦 Unique jobs: ${seen.size}`);

  // Score and process
  const processed = Array.from(seen.values()).map(j => ({
    title:    j.job_title || 'Unknown Role',
    company:  j.employer_name || 'Unknown',
    location: [j.job_city, j.job_state, j.job_country].filter(Boolean).join(', ') || 'India',
    source:   detectSource(j.job_apply_link || ''),
    url:      j.job_apply_link || '#',
    date:     j.job_posted_at_datetime_utc
                ? new Date(j.job_posted_at_datetime_utc).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})
                : 'Recent',
    desc:     (j.job_description || '').substring(0, 180) + '...',
    score:    matchScore(j.job_title, j.job_description),
    isTarget: isTargetCompany(j.employer_name || '')
  }))
  .filter(j => j.score >= 40)
  .sort((a, b) => b.score - a.score);

  console.log(`✅ After filtering: ${processed.length} jobs`);
  console.log(`   🟢 80%+: ${processed.filter(j=>j.score>=80).length}`);
  console.log(`   🟡 60-79%: ${processed.filter(j=>j.score>=60&&j.score<80).length}`);
  console.log(`   🔵 40-59%: ${processed.filter(j=>j.score>=40&&j.score<60).length}`);
  console.log(`   ⭐ Target companies: ${processed.filter(j=>j.isTarget).length}`);

  if (processed.length === 0) {
    console.log('⚠️ No jobs found. Skipping email.');
    return;
  }

  console.log('\n📧 Sending email...');
  const html = buildEmail(processed, date);
  await sendEmail(html, processed.length, date);
  console.log('✅ Done!\n');
}

main().catch(err => {
  console.error('❌ Fatal:', err);
  process.exit(1);
});
