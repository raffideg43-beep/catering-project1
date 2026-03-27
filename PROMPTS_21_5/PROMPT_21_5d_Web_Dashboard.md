# Prompt Modul 21.5d: Web Dashboard (Bagian C)

**STATUS: ✅ READY** | Est. 4-5 hours | ~900 LOC  
**Priority: 4 (After 21.5c endpoints deployed)**

---

## ⚠️ DEPENDENCIES

Must complete BEFORE starting:
- [ ] Modul 21.5c (Compliance Endpoints) — DEPLOYED & TESTED

---

## Tujuan

Build React/Next.js dashboard untuk monitoring compliance dengan charts, alerts, dan data entry forms.

---

## TUGAS 1: Layout & Components Structure

**File:** `web/app/compliance/layout.tsx` (BARU)

```tsx
'use client'

import React from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@components/ui/tabs'
import { Alert, AlertDescription } from '@components/ui/alert'
import { AlertTriangle, CheckCircle } from 'lucide-react'

export default function ComplianceLayout({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = React.useState<any[]>([])
  const [stats, setStats] = React.useState({
    anomaly_temps: 0,
    expiring_samples: 0,
    pending_incidents: 0
  })

  React.useEffect(() => {
    // Fetch alerts dari API
    Promise.all([
      fetch('/api/compliance/temperature?log_date=' + new Date().toISOString().split('T')[0])
        .then(r => r.json()),
      fetch('/api/compliance/food-samples')
        .then(r => r.json()),
      fetch('/api/compliance/incidents?month=' + (new Date().getMonth() + 1) + '&year=' + new Date().getFullYear())
        .then(r => r.json())
    ]).then(([tempRes, sampleRes, incidentRes]) => {
      const merged = []
      if (tempRes.alerts_count > 0) merged.push({
        type: 'temp', count: tempRes.alerts_count, severity: 'high'
      })
      if (sampleRes.alerts_count > 0) merged.push({
        type: 'sample', count: sampleRes.alerts_count, severity: 'medium'
      })
      if (incidentRes.data?.some((i: any) => i.status === 'investigasi')) {
        merged.push({
          type: 'incident', count: incidentRes.data.filter((i: any) => i.status === 'investigasi').length,
          severity: 'high'
        })
      }
      
      setAlerts(merged)
      setStats({
        anomaly_temps: tempRes.alerts_count,
        expiring_samples: sampleRes.alerts_count,
        pending_incidents: incidentRes.data?.length || 0
      })
    })
  }, [])

  return (
    <div className="space-y-6 p-6">
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((alert, idx) => (
            <Alert key={idx} variant={alert.severity === 'high' ? 'destructive' : 'default'}>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {alert.type === 'temp' && `⚠️ ${alert.count} anomali suhu terdeteksi`}
                {alert.type === 'sample' && `⚠️ ${alert.count} sampel akan kadaluarsa dalam 4 jam`}
                {alert.type === 'incident' && `🚨 ${alert.count} insiden dalam investigasi`}
              </AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      <Tabs defaultValue="hygiene" className="w-full">
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="hygiene">Higiene</TabsTrigger>
          <TabsTrigger value="temperature">Suhu</TabsTrigger>
          <TabsTrigger value="samples">Bank Sampel</TabsTrigger>
          <TabsTrigger value="waste">Sisa Makanan</TabsTrigger>
          <TabsTrigger value="incidents">Insiden</TabsTrigger>
          <TabsTrigger value="slhs">SLHS</TabsTrigger>
        </TabsList>

        <TabsContent value="hygiene">{children}</TabsContent>
        <TabsContent value="temperature">{children}</TabsContent>
        <TabsContent value="samples">{children}</TabsContent>
        <TabsContent value="waste">{children}</TabsContent>
        <TabsContent value="incidents">{children}</TabsContent>
        <TabsContent value="slhs">{children}</TabsContent>
      </Tabs>
    </div>
  )
}
```

---

## TUGAS 2: Hygiene Page

**File:** `web/app/compliance/hygiene/page.tsx`

```tsx
'use client'

import React from 'react'
import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@components/ui/dialog'
import { CheckCircle, AlertCircle, XCircle } from 'lucide-react'
import { format } from 'date-fns'

const AREAS = [
  'Kebersihan Lantai & Dinding',
  'Suhu Penyimpanan (Chiller/Freezer)',
  'Kebersihan Peralatan Masak',
  'Atribut Personel (Masker/Apron/Hairnet)',
  'Kualitas Air Bersih',
  'Kebersihan Area Penyimpanan',
  'Kondisi Tempat Sampah'
]

export default function HygienePage() {
  const [checks, setChecks] = useState<any[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    check_date: new Date().toISOString().split('T')[0],
    items: AREAS.map(a => ({ area: a, status: 'baik', catatan: '' })),
    notes: ''
  })

  useEffect(() => {
    const now = new Date()
    fetch(`/api/compliance/hygiene?month=${now.getMonth() + 1}&year=${now.getFullYear()}`)
      .then(r => r.json())
      .then(data => setChecks(data.data || []))
  }, [])

  const handleSubmit = async () => {
    const response = await fetch('/api/compliance/hygiene', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        check_date: formData.check_date,
        items: formData.items,
        notes: formData.notes
      })
    })

    if (response.ok) {
      const result = await response.json()
      setChecks([result.data, ...checks])
      setIsOpen(false)
      // Reset form
      setFormData({
        check_date: new Date().toISOString().split('T')[0],
        items: AREAS.map(a => ({ area: a, status: 'baik', catatan: '' })),
        notes: ''
      })
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'baik':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'perlu_perbaikan':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />
      case 'tidak_layak':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Checklist Higiene</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>+ Checklist Baru</Button>
          </DialogTrigger>
          <DialogContent className="max-h-96 overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Input Checklist Higiene</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Tanggal</label>
                <Input
                  type="date"
                  value={formData.check_date}
                  onChange={e => setFormData({ ...formData, check_date: e.target.value })}
                />
              </div>

              {formData.items.map((item, idx) => (
                <div key={idx} className="p-3 border rounded-lg">
                  <label className="text-sm font-medium">{item.area}</label>
                  <select
                    value={item.status}
                    onChange={e => {
                      const newItems = [...formData.items]
                      newItems[idx].status = e.target.value
                      setFormData({ ...formData, items: newItems })
                    }}
                    className="w-full mt-2 border rounded px-2 py-1 text-sm"
                  >
                    <option value="baik">✓ Baik</option>
                    <option value="perlu_perbaikan">⚠️ Perlu Perbaikan</option>
                    <option value="tidak_layak">✗ Tidak Layak</option>
                  </select>
                  <Input
                    placeholder="Catatan (opsional)"
                    value={item.catatan}
                    onChange={e => {
                      const newItems = [...formData.items]
                      newItems[idx].catatan = e.target.value
                      setFormData({ ...formData, items: newItems })
                    }}
                    className="mt-2 text-sm"
                  />
                </div>
              ))}

              <Input
                placeholder="Catatan umum"
                value={formData.notes}
                onChange={e => setFormData({ ...formData, notes: e.target.value })}
              />

              <Button onClick={handleSubmit} className="w-full">
                Simpan Checklist
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {checks.map(check => (
          <Card key={check.id}>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-lg">{format(new Date(check.check_date), 'dd MMMM yyyy')}</CardTitle>
                  <p className="text-sm text-gray-500 mt-1">By: {check.checked_by}</p>
                </div>
                <div className="flex items-center gap-2">
                  {getStatusIcon(check.overall_status)}
                  <span className="font-semibold capitalize">{check.overall_status}</span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                {check.items?.map((item: any, idx: number) => (
                  <div key={idx} className="flex items-start gap-2 p-2 bg-gray-50 rounded">
                    {getStatusIcon(item.status)}
                    <div className="text-sm">
                      <p className="font-medium">{item.area}</p>
                      {item.catatan && <p className="text-gray-600">{item.catatan}</p>}
                    </div>
                  </div>
                ))}
              </div>
              {check.notes && (
                <div className="mt-3 p-2 bg-blue-50 rounded text-sm">
                  <strong>Catatan:</strong> {check.notes}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

---

## TUGAS 3: Temperature & Samples Pages

**File:** `web/app/compliance/temperature/page.tsx`

```tsx
'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@components/ui/dialog'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { AlertCircle } from 'lucide-react'

const AREAS = ['gudang_kering', 'chiller', 'freezer']
const LIMITS = {
  gudang_kering: { min: 0, max: 25 },
  chiller: { min: 10, max: 15 },
  freezer: { min: -30, max: -18 }
}

export default function TemperaturePage() {
  const [logs, setLogs] = useState<any[]>([])
  const [chartData, setChartData] = useState<any[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    log_date: new Date().toISOString().split('T')[0],
    log_time: '08:00',
    area: 'chiller',
    temperature: ''
  })

  useEffect(() => {
    const today = new Date().toISOString().split('T')[0]
    fetch(`/api/compliance/temperature?log_date=${today}`)
      .then(r => r.json())
      .then(data => {
        setLogs(data.data || [])
        
        // Prepare chart data
        const grouped: any = {}
        ;(data.data || []).forEach((log: any) => {
          const time = log.log_time
          if (!grouped[time]) grouped[time] = {}
          grouped[time][log.area] = log.temperature
        })
        
        const chartPoints = Object.entries(grouped).map(([time, temps]: [string, any]) => ({
          time,
          ...temps
        }))
        setChartData(chartPoints)
      })
  }, [])

  const handleSubmit = async () => {
    const response = await fetch('/api/compliance/temperature', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        log_date: formData.log_date,
        log_time: formData.log_time,
        area: formData.area,
        temperature: parseFloat(formData.temperature)
      })
    })

    if (response.ok) {
      const result = await response.json()
      setLogs([result.data, ...logs])
      setIsOpen(false)
      setFormData({
        log_date: new Date().toISOString().split('T')[0],
        log_time: '08:00',
        area: 'chiller',
        temperature: ''
      })
    }
  }

  const anomalies = logs.filter(l => !l.is_normal)

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Monitoring Suhu</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>+ Catat Suhu</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Catat Suhu Penyimpanan</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Tanggal</label>
                <Input
                  type="date"
                  value={formData.log_date}
                  onChange={e => setFormData({ ...formData, log_date: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Jam</label>
                <Input
                  type="time"
                  value={formData.log_time}
                  onChange={e => setFormData({ ...formData, log_time: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Area</label>
                <select
                  value={formData.area}
                  onChange={e => setFormData({ ...formData, area: e.target.value })}
                  className="w-full border rounded px-2 py-2"
                >
                  {AREAS.map(a => (
                    <option key={a} value={a}>
                      {a} ({LIMITS[a as keyof typeof LIMITS].min}-{LIMITS[a as keyof typeof LIMITS].max}°C)
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Suhu (°C)</label>
                <Input
                  type="number"
                  step="0.1"
                  value={formData.temperature}
                  onChange={e => setFormData({ ...formData, temperature: e.target.value })}
                  placeholder="Contoh: 12.5"
                />
              </div>
              <Button onClick={handleSubmit} className="w-full">
                Simpan
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {anomalies.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex gap-2">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-900">⚠️ Anomali Suhu Terdeteksi</h3>
              <ul className="mt-2 space-y-1 text-sm text-red-800">
                {anomalies.map((a, i) => (
                  <li key={i}>
                    {a.area}: {a.temperature}°C pada {a.log_time}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {chartData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Grafik Suhu Harian</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="gudang_kering" stroke="#FFB84D" />
                <Line type="monotone" dataKey="chiller" stroke="#4DA6FF" />
                <Line type="monotone" dataKey="freezer" stroke="#66B2FF" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Log Suhu ({logs.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">Jam</th>
                  <th className="text-left px-3 py-2">Area</th>
                  <th className="text-right px-3 py-2">Suhu (°C)</th>
                  <th className="text-center px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id} className="border-t">
                    <td className="px-3 py-2">{log.log_time}</td>
                    <td className="px-3 py-2">{log.area}</td>
                    <td className="text-right px-3 py-2 font-mono">{log.temperature}</td>
                    <td className="text-center px-3 py-2">
                      {log.is_normal ? '✓' : '⚠️'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

**File:** `web/app/compliance/samples/page.tsx`

```tsx
'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@components/ui/dialog'
import { AlertCircle, Clock, Check, Trash2 } from 'lucide-react'
import { format } from 'date-fns'

export default function SamplesPage() {
  const [samples, setSamples] = useState<any[]>([])
  const [alerts, setAlerts] = useState<any[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    sample_date: new Date().toISOString().split('T')[0],
    menu_name: '',
    taken_at: '08:00',
    weight_gram: 50,
    storage_temp: ''
  })

  useEffect(() => {
    fetch('/api/compliance/food-samples')
      .then(r => r.json())
      .then(data => {
        setSamples(data.data || [])
        setAlerts(data.alerts || [])
      })
  }, [])

  const handleSubmit = async () => {
    const response = await fetch('/api/compliance/food-samples', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sample_date: formData.sample_date,
        menu_name: formData.menu_name,
        taken_at: formData.taken_at,
        weight_gram: parseFloat(formData.weight_gram.toString()),
        storage_temp: formData.storage_temp ? parseFloat(formData.storage_temp) : null
      })
    })

    if (response.ok) {
      const result = await response.json()
      setSamples([result.data, ...samples])
      setIsOpen(false)
    }
  }

  const handleDispose = async (sampleId: string) => {
    const response = await fetch(`/api/compliance/food-samples/${sampleId}/dispose`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'normal_disposal' })
    })

    if (response.ok) {
      setSamples(samples.map(s => s.id === sampleId ? { ...s, status: 'dibuang' } : s))
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Bank Sampel Makanan</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>+ Ambil Sampel</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Catat Sampel Makanan Baru</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium">Tanggal Ambil</label>
                <Input
                  type="date"
                  value={formData.sample_date}
                  onChange={e => setFormData({ ...formData, sample_date: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Menu</label>
                <Input
                  value={formData.menu_name}
                  onChange={e => setFormData({ ...formData, menu_name: e.target.value })}
                  placeholder="Contoh: Nasi Goreng"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Jam Ambil</label>
                <Input
                  type="time"
                  value={formData.taken_at}
                  onChange={e => setFormData({ ...formData, taken_at: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Berat (g)</label>
                <Input
                  type="number"
                  value={formData.weight_gram}
                  onChange={e => setFormData({ ...formData, weight_gram: parseFloat(e.target.value) })}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Suhu Penyimpanan (°C)</label>
                <Input
                  type="number"
                  step="0.1"
                  value={formData.storage_temp}
                  onChange={e => setFormData({ ...formData, storage_temp: e.target.value })}
                  placeholder="Opsional"
                />
              </div>
              <Button onClick={handleSubmit} className="w-full">
                Simpan Sampel
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {alerts.length > 0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <div className="flex gap-2">
            <Clock className="h-5 w-5 text-orange-500 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-orange-900">⚠️ Sampel Akan Kadaluarsa</h3>
              <ul className="mt-2 space-y-1 text-sm text-orange-800">
                {alerts.map((a, i) => (
                  <li key={i}>
                    {a.sample_code} ({a.menu}) — {a.hours_left.toFixed(1)} jam lagi
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4">
        {samples.map(sample => (
          <Card key={sample.id} className={sample.status === 'dibuang' ? 'opacity-50' : ''}>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-lg">{sample.sample_code}</CardTitle>
                  <p className="text-sm text-gray-600">{sample.menu_name}</p>
                </div>
                <div className="flex items-center gap-2">
                  {sample.hours_remaining && sample.hours_remaining <= 4 ? (
                    <AlertCircle className="h-5 w-5 text-orange-500" />
                  ) : (
                    <Check className="h-5 w-5 text-green-500" />
                  )}
                  <span className="text-sm font-medium">{sample.status}</span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 text-sm">
                <p>Diambil: {format(new Date(sample.sample_date + 'T' + sample.taken_at), 'dd MMM HH:mm')}</p>
                <p>Kadaluarsa: {format(new Date(sample.expires_at), 'dd MMM HH:mm')}</p>
                {sample.hours_remaining && (
                  <p className="font-semibold">
                    {sample.hours_remaining > 0
                      ? `⏱️ ${sample.hours_remaining.toFixed(1)} jam lagi`
                      : '❌ Sudah kadaluarsa'}
                  </p>
                )}
                <div className="flex gap-2 mt-3">
                  {sample.status === 'disimpan' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDispose(sample.id)}
                    >
                      <Trash2 className="h-4 w-4 mr-1" />
                      Buang
                    </Button>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

---

## TUGAS 4: Food Waste & Incidents Pages

**File:** `web/app/compliance/waste/page.tsx`

```tsx
'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@components/ui/dialog'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export default function FoodWastePage() {
  const [reports, setReports] = useState<any[]>([])
  const [chartData, setChartData] = useState<any[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [month, setMonth] = useState(new Date().getMonth() + 1)
  const [year, setYear] = useState(new Date().getFullYear())
  const [formData, setFormData] = useState({
    delivery_id: '',
    school_id: '',
    report_date: new Date().toISOString().split('T')[0],
    portions_sent: '',
    portions_consumed: '',
    comstock_score: 5,
    waste_reason: ''
  })

  useEffect(() => {
    fetch(`/api/compliance/food-waste?month=${month}&year=${year}`)
      .then(r => r.json())
      .then(data => {
        setReports(data.data || [])
        
        // Prepare chart data from summary
        const chartPoints = Object.entries(data.summary || {}).map(([schoolId, stats]: [string, any]) => ({
          school: schoolId?.substring(0, 8),
          waste_pct: stats.waste_pct,
          comstock: stats.avg_comstock
        }))
        setChartData(chartPoints)
      })
  }, [month, year])

  const handleSubmit = async () => {
    const response = await fetch('/api/compliance/food-waste', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        delivery_id: formData.delivery_id,
        school_id: formData.school_id,
        report_date: formData.report_date,
        portions_sent: parseInt(formData.portions_sent),
        portions_consumed: parseInt(formData.portions_consumed),
        comstock_score: parseInt(formData.comstock_score.toString()),
        waste_reason: formData.waste_reason
      })
    })

    if (response.ok) {
      const result = await response.json()
      setReports([result.data, ...reports])
      setIsOpen(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Laporan Sisa Makanan</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>+ Laporan Baru</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Input Laporan Sisa Makanan</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                placeholder="ID Pengiriman"
                value={formData.delivery_id}
                onChange={e => setFormData({ ...formData, delivery_id: e.target.value })}
              />
              <Input
                placeholder="ID Sekolah"
                value={formData.school_id}
                onChange={e => setFormData({ ...formData, school_id: e.target.value })}
              />
              <Input
                type="date"
                value={formData.report_date}
                onChange={e => setFormData({ ...formData, report_date: e.target.value })}
              />
              <div>
                <label className="text-sm font-medium">Porsi Dikirim</label>
                <Input
                  type="number"
                  value={formData.portions_sent}
                  onChange={e => setFormData({ ...formData, portions_sent: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Porsi Dikonsumsi</label>
                <Input
                  type="number"
                  value={formData.portions_consumed}
                  onChange={e => setFormData({ ...formData, portions_consumed: e.target.value })}
                />
              </div>
              <div>
                <label className="text-sm font-medium">Skor Comstock (1-5)</label>
                <select
                  value={formData.comstock_score}
                  onChange={e => setFormData({ ...formData, comstock_score: parseInt(e.target.value) })}
                  className="w-full border rounded px-2 py-2"
                >
                  <option value="1">1 - Sangat Kurang</option>
                  <option value="2">2 - Kurang</option>
                  <option value="3">3 - Cukup</option>
                  <option value="4">4 - Baik</option>
                  <option value="5">5 - Sangat Baik</option>
                </select>
              </div>
              <Input
                placeholder="Alasan Sisa"
                value={formData.waste_reason}
                onChange={e => setFormData({ ...formData, waste_reason: e.target.value })}
              />
              <Button onClick={handleSubmit} className="w-full">
                Simpan Laporan
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex gap-2 items-center">
        <select
          value={month}
          onChange={e => setMonth(parseInt(e.target.value))}
          className="border rounded px-2 py-2"
        >
          {Array.from({ length: 12 }).map((_, i) => (
            <option key={i + 1} value={i + 1}>
              {new Date(2024, i).toLocaleString('id-ID', { month: 'long' })}
            </option>
          ))}
        </select>
        <select
          value={year}
          onChange={e => setYear(parseInt(e.target.value))}
          className="border rounded px-2 py-2"
        >
          <option value={2024}>2024</option>
          <option value={2025}>2025</option>
        </select>
      </div>

      {chartData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Analisis Sisa Makanan</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="school" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="waste_pct" fill="#FF6B6B" name="% Sisa" />
                <Bar dataKey="comstock" fill="#4ECDC4" name="Skor Comstock" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Laporan ({reports.length})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">Tanggal</th>
                  <th className="text-left px-3 py-2">Sekolah</th>
                  <th className="text-right px-3 py-2">Kirim</th>
                  <th className="text-right px-3 py-2">Konsumsi</th>
                  <th className="text-right px-3 py-2">% Sisa</th>
                  <th className="text-center px-3 py-2">Comstock</th>
                </tr>
              </thead>
              <tbody>
                {reports.map(report => (
                  <tr key={report.id} className="border-t">
                    <td className="px-3 py-2">{report.report_date}</td>
                    <td className="px-3 py-2">{report.school_id.substring(0, 8)}</td>
                    <td className="text-right px-3 py-2">{report.portions_sent}</td>
                    <td className="text-right px-3 py-2">{report.portions_consumed}</td>
                    <td className="text-right px-3 py-2 font-semibold">{report.waste_pct}%</td>
                    <td className="text-center px-3 py-2">⭐{report.comstock_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

---

## TUGAS 5: Incidents & SLHS Pages

**File:** `web/app/compliance/incidents/page.tsx`

```tsx
'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@components/ui/dialog'
import { AlertTriangle } from 'lucide-react'
import { format } from 'date-fns'

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<any[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    school_id: '',
    incident_time: new Date().toISOString().substring(0, 16),
    location: '',
    victim_count: '',
    symptoms: [''],
    first_action: '',
    sample_secured: false
  })

  useEffect(() => {
    const now = new Date()
    fetch(`/api/compliance/incidents?month=${now.getMonth() + 1}&year=${now.getFullYear()}`)
      .then(r => r.json())
      .then(data => setIncidents(data.data || []))
  }, [])

  const handleSubmit = async () => {
    const response = await fetch('/api/compliance/incidents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        school_id: formData.school_id,
        incident_time: formData.incident_time,
        location: formData.location,
        victim_count: parseInt(formData.victim_count),
        symptoms: formData.symptoms.filter(s => s),
        first_action: formData.first_action,
        sample_secured: formData.sample_secured
      })
    })

    if (response.ok) {
      const result = await response.json()
      setIncidents([result.data, ...incidents])
      setIsOpen(false)
    }
  }

  const pendingCount = incidents.filter(i => i.status === 'investigasi').length

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Laporan Insiden</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>+ Laporkan Insiden</Button>
          </DialogTrigger>
          <DialogContent className="max-h-96 overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Laporan Insiden KLB</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                placeholder="ID Sekolah"
                value={formData.school_id}
                onChange={e => setFormData({ ...formData, school_id: e.target.value })}
              />
              <Input
                type="datetime-local"
                value={formData.incident_time}
                onChange={e => setFormData({ ...formData, incident_time: e.target.value })}
              />
              <Input
                placeholder="Lokasi"
                value={formData.location}
                onChange={e => setFormData({ ...formData, location: e.target.value })}
              />
              <Input
                type="number"
                placeholder="Jumlah Korban"
                value={formData.victim_count}
                onChange={e => setFormData({ ...formData, victim_count: e.target.value })}
              />
              <div>
                <label className="text-sm font-medium">Gejala (Pisahkan dengan Enter)</label>
                {formData.symptoms.map((sym, idx) => (
                  <Input
                    key={idx}
                    placeholder="Contoh: Muntah, Diare"
                    value={sym}
                    onChange={e => {
                      const newSym = [...formData.symptoms]
                      newSym[idx] = e.target.value
                      setFormData({ ...formData, symptoms: newSym })
                    }}
                    className="mt-1"
                  />
                ))}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setFormData({ ...formData, symptoms: [...formData.symptoms, ''] })}
                  className="mt-2"
                >
                  + Tambah Gejala
                </Button>
              </div>
              <Input
                placeholder="Tindakan Pertama"
                value={formData.first_action}
                onChange={e => setFormData({ ...formData, first_action: e.target.value })}
              />
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.sample_secured}
                  onChange={e => setFormData({ ...formData, sample_secured: e.target.checked })}
                />
                <span className="text-sm">Sampel Diamankan</span>
              </label>
              <Button onClick={handleSubmit} className="w-full">
                Kirim Laporan
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {pendingCount > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex gap-2">
            <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-red-900">🚨 Ada {pendingCount} Insiden Dalam Investigasi</h3>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {incidents.map(incident => (
          <Card
            key={incident.id}
            className={incident.status === 'investigasi' ? 'border-red-300 bg-red-50' : ''}
          >
            <CardHeader className="pb-2">
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-lg">{incident.incident_code}</CardTitle>
                  <p className="text-sm text-gray-600">
                    {format(new Date(incident.incident_time), 'dd MMM yyyy HH:mm')}
                  </p>
                </div>
                <span className={`px-3 py-1 rounded text-sm font-medium ${
                  incident.status === 'investigasi'
                    ? 'bg-red-200 text-red-900'
                    : 'bg-green-200 text-green-900'
                }`}>
                  {incident.status}
                </span>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <p><strong>Lokasi:</strong> {incident.location}</p>
              <p><strong>Korban:</strong> {incident.victim_count} orang</p>
              <p><strong>Gejala:</strong> {incident.symptoms?.join(', ') || '-'}</p>
              <p><strong>Sampel:</strong> {incident.sample_secured ? '✓ Diamankan' : '✗ Tidak'}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

**File:** `web/app/compliance/slhs/page.tsx`

```tsx
'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@components/ui/card'
import { Button } from '@components/ui/button'
import { Input } from '@components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@components/ui/dialog'
import { AlertCircle, Calendar } from 'lucide-react'

export default function SLHSPage() {
  const [slhsList, setSLHSList] = useState<any[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [formData, setFormData] = useState({
    cert_number: '',
    issued_date: '',
    expires_date: '',
    label_expires: '',
    file_url: ''
  })

  useEffect(() => {
    fetch('/api/compliance/slhs')
      .then(r => r.json())
      .then(data => setSLHSList(data.data || []))
  }, [])

  const handleSubmit = async () => {
    const response = await fetch('/api/compliance/slhs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    })

    if (response.ok) {
      const result = await response.json()
      setSLHSList([result.data, ...slhsList])
      setIsOpen(false)
    }
  }

  const expiringCount = slhsList.filter(s => {
    const expires = new Date(s.expires_date)
    const daysLeft = (expires.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)
    return daysLeft <= 30
  }).length

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Dokumen SLHS</h1>
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
          <DialogTrigger asChild>
            <Button>+ Sertifikat Baru</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Tambah Dokumen SLHS</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <Input
                placeholder="Nomor Sertifikat"
                value={formData.cert_number}
                onChange={e => setFormData({ ...formData, cert_number: e.target.value })}
              />
              <Input
                type="date"
                label="Tanggal Terbit"
                value={formData.issued_date}
                onChange={e => setFormData({ ...formData, issued_date: e.target.value })}
              />
              <Input
                type="date"
                label="Tanggal Kadaluarsa"
                value={formData.expires_date}
                onChange={e => setFormData({ ...formData, expires_date: e.target.value })}
              />
              <Input
                type="date"
                label="Label Habis (Jika Ada)"
                value={formData.label_expires}
                onChange={e => setFormData({ ...formData, label_expires: e.target.value })}
              />
              <Input
                placeholder="URL Dokumen"
                value={formData.file_url}
                onChange={e => setFormData({ ...formData, file_url: e.target.value })}
              />
              <Button onClick={handleSubmit} className="w-full">
                Simpan SLHS
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {expiringCount > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex gap-2">
            <Calendar className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="font-semibold text-yellow-900">📅 {expiringCount} Sertifikat Kadaluarsa Dalam 30 Hari</h3>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {slhsList.map(slhs => {
          const expires = new Date(slhs.expires_date)
          const daysLeft = (expires.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24)
          const isExpiring = daysLeft <= 30

          return (
            <Card key={slhs.id} className={isExpiring ? 'border-yellow-300 bg-yellow-50' : ''}>
              <CardHeader className="pb-2">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle>{slhs.cert_number}</CardTitle>
                    <p className="text-sm text-gray-600 mt-1">
                      Terbit: {new Date(slhs.issued_date).toLocaleDateString('id-ID')}
                    </p>
                  </div>
                  <div className="text-right">
                    {isExpiring ? (
                      <div className="flex items-center gap-1 text-yellow-700">
                        <AlertCircle className="h-4 w-4" />
                        <span className="font-semibold">{Math.ceil(daysLeft)} hari</span>
                      </div>
                    ) : (
                      <span className="text-green-700 font-semibold">{Math.ceil(daysLeft)} hari</span>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm">Kadaluarsa: {new Date(slhs.expires_date).toLocaleDateString('id-ID')}</p>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
```

---

## TESTING CHECKLIST

- [ ] Dashboard alerts load ✓
- [ ] Higiene form submission ✓
- [ ] Higiene checklist display ✓
- [ ] Temperature form + chart ✓
- [ ] Anomaly alerts show ✓
- [ ] Food samples auto-expire timer ✓
- [ ] Food waste chart + summary ✓
- [ ] Incident form + pending counter ✓
- [ ] SLHS expiration alerts ✓
- [ ] All responsive on mobile ✓

---

## GIT COMMIT

```bash
git add web/app/compliance/
git commit -m "feat: compliance dashboard — higiene, suhu, sampel, sisa, insiden, SLHS (Modul 21.5d)"
```

**NEXT**: Complete 21.5e (Export Sheets).
