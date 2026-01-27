import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type ProcessStep = {
  title: string
  description: string
  outcome: string
  label: string
}

type ExtractedLine = {
  id: number
  order_id: number
  product_id?: number
  customer_name: string
  extracted_text: string
  normalized_name: string
  quantity: number
  status: 'matched' | 'needs-review'
}

type Customer = {
  id: number
  name: string
  language?: string
}

type Product = {
  id: number
  internal_name: string
  base_price: number
  description?: string
}

type CustomerPricingEntry = {
  id: number
  customer_id: number
  product_id: number
  override_price: number
  created_at: string
}

type ProductAliasEntry = {
  id: number
  product_id: number
  alias_name: string
}

const processSteps: ProcessStep[] = [
  {
    title: 'Order intake',
    description:
      'Upload fax PDFs, pull text via Cloud OCR, and show the extracted lines for confirmation.',
    outcome: 'Sales order row ready for review',
    label: '01',
  },
  {
    title: 'Product master',
    description:
      'Match extracted names to internal products or register new aliases for future orders.',
    outcome: 'Consistent inventory naming and pricing',
    label: '02',
  },
  {
    title: 'Customer & pricing',
    description:
      'Select customer-specific pricing overrides that are remembered automatically.',
    outcome: 'Accurate invoices every time',
    label: '03',
  },
  {
    title: 'Purchase data',
    description:
      'Manually track purchases so the base price reflects recent costs without OCR noise.',
    outcome: 'Clean product cost history',
    label: '04',
  },
  {
    title: 'PDF generation',
    description:
      'Render packing slips, delivery notes, and invoices from fixed HTML templates.',
    outcome: 'Ready-to-print documents per customer',
    label: '05',
  },
]

const pdfDeliverables = [
  {
    title: 'Packing Slip (現品票)',
    detail: 'One PDF per product line with delivery number, units, product name, and quantity.',
  },
  {
    title: 'Delivery Note (納品書)',
    detail: 'Summarizes delivered quantities and references the matching packing slips.',
  },
  {
    title: 'Invoice (請求書)',
    detail: 'Includes unit price, totals, and customer pricing metadata.',
  },
]

const quickStats = [
  { label: 'Human confirmation', value: '100% required', detail: 'OCR is never auto-approved' },
  { label: 'Target reduction', value: '70–80%', detail: 'Cut manual re-entry for 200-line faxes' },
  { label: 'Users', value: '1–3 operators', detail: 'Desktop-only, Japanese UI' },
]

const nonFunctionalFocus = [
  'Single-role login with manual backup/export workflows',
  'Stable, predictable behavior over clever automation',
  'SQLite schema ready to migrate to PostgreSQL/RDS',
  'Office desktop layout, no mobile or SPA complexity',
  'Explicitly keep out inventory/stock/accounting integrations',
]

const pdfDocumentTypes = [
  { label: 'Packing slips', value: 'packing' },
  { label: 'Delivery notes', value: 'delivery' },
  { label: 'Invoices', value: 'invoice' },
]

const parseJson = async <T,>(response: Response): Promise<T> => {
  const text = await response.text()
  const data = text ? JSON.parse(text) : {}
  if (!response.ok) {
    const detail = (data as { detail?: string }).detail ?? response.statusText ?? 'Request failed'
    throw new Error(detail)
  }
  return data as T
}

function App() {
  const [customers, setCustomers] = useState<Customer[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [aliasList, setAliasList] = useState<ProductAliasEntry[]>([])
  const [pricingOverrides, setPricingOverrides] = useState<CustomerPricingEntry[]>([])
  const [orderLines, setOrderLines] = useState<ExtractedLine[]>([])
  const [orderId, setOrderId] = useState<number | null>(null)
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | ''>('')
  const [aliasProductId, setAliasProductId] = useState<number | ''>('')
  const [aliasName, setAliasName] = useState('')
  const [pricingProductId, setPricingProductId] = useState<number | ''>('')
  const [pricingValue, setPricingValue] = useState('')
  const [purchaseProductId, setPurchaseProductId] = useState<number | ''>('')
  const [purchaseValue, setPurchaseValue] = useState('')
  const [loadingLines, setLoadingLines] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [orderMessage, setOrderMessage] = useState('Upload a fax PDF to start the workflow.')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [aliasError, setAliasError] = useState<string | null>(null)
  const [pricingError, setPricingError] = useState<string | null>(null)
  const [purchaseMessage, setPurchaseMessage] = useState<string | null>(null)
  const [pdfMessage, setPdfMessage] = useState<string | null>(null)
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState<string | null>(null)
  const [fileInputKey, setFileInputKey] = useState(Date.now())

  const productNameMap = useMemo(() => {
    const map = new Map<number, string>()
    products.forEach((product) => map.set(product.id, product.internal_name))
    return map
  }, [products])

  const selectedCustomer = customers.find(
    (customer) => customer.id === selectedCustomerId,
  )

  useEffect(() => {
    const fetchData = async () => {
      try {
        const customerResponse = await fetch(`${API_BASE_URL}/api/customers`)
        const customerData = await parseJson<Customer[]>(customerResponse)
        setCustomers(customerData)
        setSelectedCustomerId((prevSelected) => {
          if (prevSelected) {
            return prevSelected
          }
          return customerData.length ? customerData[0].id : prevSelected
        })
      } catch (error) {
        console.error(error)
      }

      try {
        const productResponse = await fetch(`${API_BASE_URL}/api/products`)
        const productData = await parseJson<Product[]>(productResponse)
        setProducts(productData)
      } catch (error) {
        console.error(error)
      }

      try {
        const aliasResponse = await fetch(`${API_BASE_URL}/api/products/aliases`)
        const aliasData = await parseJson<ProductAliasEntry[]>(aliasResponse)
        setAliasList(aliasData)
      } catch (error) {
        console.error(error)
      }
    }

    fetchData()
  }, [])

  useEffect(() => {
    if (!selectedCustomerId) {
      setPricingOverrides([])
      return
    }

    const fetchPricing = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/customers/${selectedCustomerId}/pricing`,
        )
        const data = await parseJson<CustomerPricingEntry[]>(response)
        setPricingOverrides(data)
      } catch (error) {
        setPricingOverrides([])
        console.error(error)
      }
    }

    fetchPricing()
  }, [selectedCustomerId])

  const fetchOrderLines = async (id: number) => {
    setLoadingLines(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/orders/${id}/lines`)
      const data = await parseJson<ExtractedLine[]>(response)
      setOrderLines(data)
      setOrderMessage(`Order ${id} ready for confirmation.`)
    } catch (error) {
      setOrderLines([])
      setOrderMessage('Failed to load lines. Please retry.')
      setUploadError(error instanceof Error ? error.message : 'Failed to load lines')
    } finally {
      setLoadingLines(false)
    }
  }

  const handleUpload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setUploadError(null)
    const formData = new FormData(event.currentTarget)
    const file = formData.get('faxFile') as File | null
    if (!file) {
      setUploadError('ファイルを選択してください')
      return
    }
    if (typeof selectedCustomerId !== 'number') {
      setUploadError('顧客を選択してください')
      return
    }

    setUploading(true)
    setOrderMessage('Uploading and running OCR preview...')
    try {
      const payload = new FormData()
      payload.append('file', file)
      payload.append('customer_id', String(selectedCustomerId))
      const response = await fetch(`${API_BASE_URL}/api/orders/upload`, {
        method: 'POST',
        body: payload,
      })
      const result = await parseJson<{ order_id: number; status: string; stored_path: string }>(
        response,
      )
      setOrderId(result.order_id)
      await fetchOrderLines(result.order_id)
      setPdfMessage(null)
      setPdfPreviewUrl(null)
      setOrderMessage('OCR preview ready — confirm and save the order.')
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Upload failed')
    } finally {
      setUploading(false)
      setFileInputKey(Date.now())
    }
  }

  const handleAliasSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setAliasError(null)
    if (!aliasProductId || !aliasName.trim()) {
      setAliasError('商品とエイリアス名を入力してください。')
      return
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/products/aliases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_id: aliasProductId,
          alias_name: aliasName.trim(),
        }),
      })
      await parseJson<ProductAliasEntry>(response)
      setAliasName('')
      setAliasProductId('')
      const refreshed = await fetch(`${API_BASE_URL}/api/products/aliases`)
      const aliasData = await parseJson<ProductAliasEntry[]>(refreshed)
      setAliasList(aliasData)
    } catch (error) {
      setAliasError(error instanceof Error ? error.message : 'Failed to add alias.')
    }
  }

  const handlePricingSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPricingError(null)
    if (!selectedCustomerId) {
      setPricingError('顧客を選択してください。')
      return
    }
    if (!pricingProductId || !pricingValue.trim()) {
      setPricingError('商品と価格を入力してください。')
      return
    }
    const value = Number(pricingValue)
    if (Number.isNaN(value)) {
      setPricingError('無効な価格です。')
      return
    }
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/customers/${selectedCustomerId}/pricing`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product_id: pricingProductId,
            override_price: value,
          }),
        },
      )
      await parseJson<CustomerPricingEntry>(response)
      setPricingProductId('')
      setPricingValue('')
      setPricingError(null)
      const refreshed = await fetch(
        `${API_BASE_URL}/api/customers/${selectedCustomerId}/pricing`,
      )
      const pricingData = await parseJson<CustomerPricingEntry[]>(refreshed)
      setPricingOverrides(pricingData)
    } catch (error) {
      setPricingError(error instanceof Error ? error.message : '設定に失敗しました。')
    }
  }

  const handlePurchaseSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPurchaseMessage(null)
    if (!purchaseProductId || !purchaseValue.trim()) {
      setPurchaseMessage('商品と価格を選択してください。')
      return
    }
    const value = Number(purchaseValue)
    if (Number.isNaN(value)) {
      setPurchaseMessage('有効な価格を入力してください。')
      return
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/purchases`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product_id: purchaseProductId,
          purchase_price: value,
        }),
      })
      await parseJson<unknown>(response)
      setPurchaseProductId('')
      setPurchaseValue('')
      setPurchaseMessage('仕入れが記録され、基準価格を更新しました。')
    } catch (error) {
      setPurchaseMessage(error instanceof Error ? error.message : '仕入れの記録に失敗しました。')
    }
  }

  const handlePdfRender = async (documentType: 'packing' | 'delivery' | 'invoice') => {
    if (!orderId) {
      setPdfMessage('まずオーダーをアップロードしてください。')
      return
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/pdf/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order_id: orderId, document_type: documentType }),
      })
      const preview = await parseJson<{ preview_url: string; message: string }>(response)
      setPdfPreviewUrl(preview.preview_url)
      setPdfMessage(preview.message)
    } catch (error) {
      setPdfMessage(error instanceof Error ? error.message : 'プレビューの作成に失敗しました。')
    }
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <span className="hero-tag">FAX Order Automation MVP</span>
        <h1>Bring faxed fastener orders into a verified digital workflow.</h1>
        <p className="hero-subtitle">
          Upload fax PDFs, confirm OCR results, enrich them with product/customer knowledge, and output
          the packing slips, delivery notes, and invoices your team prints every day.
        </p>
        <div className="hero-actions">
          <button type="button">Start order intake</button>
          <button type="button" className="ghost">
            Review PDF templates
          </button>
        </div>
        <div className="hero-meta">
          <span>Frontend: React + TypeScript</span>
          <span>Backend: Python 3.10+ + FastAPI (AWS ready)</span>
          <span>OCR: Google Cloud Vision integrated via API workflows</span>
        </div>
        <div className="quick-stats">
          {quickStats.map((stat) => (
            <article className="stat-card" key={stat.label}>
              <span className="stat-value">{stat.value}</span>
              <span className="stat-label">{stat.label}</span>
              <p>{stat.detail}</p>
            </article>
          ))}
        </div>
      </header>

      <section className="process-grid">
        {processSteps.map((step) => (
          <article className="process-card" key={step.title}>
            <div className="process-label">{step.label}</div>
            <h3>{step.title}</h3>
            <p>{step.description}</p>
            <small>{step.outcome}</small>
          </article>
        ))}
      </section>

      <section className="workflow-grid">
        <article className="panel">
          <div className="panel-heading">
            <h2>Order intake</h2>
            <p>Upload a fax PDF, assign a customer, and confirm the OCR preview before saving.</p>
          </div>
          <form className="panel-form" onSubmit={handleUpload}>
            <label>
              Customer
              <select
                value={selectedCustomerId}
                onChange={(event) => {
                  const value = event.target.value
                  setSelectedCustomerId(value ? Number(value) : '')
                }}
              >
                <option value="">顧客を選択</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Fax PDF
              <input key={fileInputKey} name="faxFile" type="file" accept=".pdf" />
            </label>
            <div className="ocr-controls">
              <button type="submit" disabled={uploading}>
                {uploading ? 'Uploading...' : 'Run OCR preview'}
              </button>
              <button type="button" className="ghost" disabled>
                Save as sales order
              </button>
            </div>
          </form>
          {uploadError && <p className="status-message error">{uploadError}</p>}
          <p className="status-message">{orderMessage}</p>
          {orderId && <p className="order-id">Order ID: {orderId}</p>}
          {loadingLines ? (
            <p className="status-message">Loading OCR lines...</p>
          ) : orderLines.length ? (
            <div className="table-grid">
              <div className="table-row table-header">
                <span>Customer product</span>
                <span>Extracted</span>
                <span>Normalized</span>
                <span>Qty</span>
                <span>Status</span>
              </div>
              {orderLines.map((line) => (
                <div className="table-row" key={line.id}>
                  <input value={line.customer_name} readOnly />
                  <input value={line.extracted_text} readOnly />
                  <input value={line.normalized_name} readOnly />
                  <input value={String(line.quantity)} readOnly />
                  <span className={`status-chip status-${line.status}`}>{line.status}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="table-placeholder">No lines yet. Upload a PDF to generate OCR rows.</p>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>Product master</h2>
            <p>Link customer names to internal SKUs and keep alias history for better OCR matching.</p>
          </div>
          <form className="panel-form" onSubmit={handleAliasSubmit}>
            <label>
              Internal product
              <select
                value={aliasProductId}
                onChange={(event) => {
                  const value = event.target.value
                  setAliasProductId(value ? Number(value) : '')
                }}
              >
                <option value="">商品を選択</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.internal_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Alias to register
              <input
                value={aliasName}
                onChange={(event) => setAliasName(event.target.value)}
                placeholder="Customer keyword (ウイングナットなど)"
              />
            </label>
            <button type="submit">Register alias</button>
          </form>
          {aliasError && <p className="status-message error">{aliasError}</p>}
          <div className="alias-list">
            <h4>Known aliases</h4>
            {aliasList.length ? (
              aliasList.map((alias) => (
                <div key={alias.id} className="alias-row">
                  <span>{productNameMap.get(alias.product_id) ?? `ID ${alias.product_id}`}</span>
                  <span>{alias.alias_name}</span>
                </div>
              ))
            ) : (
              <p>No aliases recorded yet.</p>
            )}
          </div>
        </article>
      </section>

      <section className="panel-grid-two">
        <article className="panel">
          <div className="panel-heading">
            <h2>Customer & pricing</h2>
            <p>Persist overrides and purchases so invoices and base prices stay accurate.</p>
          </div>
          <form className="panel-form" onSubmit={handlePricingSubmit}>
            <label>
              Customer
              <select
                value={selectedCustomerId}
                onChange={(event) => {
                  const value = event.target.value
                  setSelectedCustomerId(value ? Number(value) : '')
                }}
              >
                <option value="">顧客を選択</option>
                {customers.map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Product
              <select
                value={pricingProductId}
                onChange={(event) => {
                  const value = event.target.value
                  setPricingProductId(value ? Number(value) : '')
                }}
              >
                <option value="">商品を選択</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.internal_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Override price
              <input
                value={pricingValue}
                onChange={(event) => setPricingValue(event.target.value)}
                placeholder="¥62.00"
              />
            </label>
            <button type="submit">Save pricing override</button>
            {pricingError && <p className="status-message error">{pricingError}</p>}
          </form>
          <div className="pricing-grid">
            {pricingOverrides.length ? (
              pricingOverrides.map((entry) => (
                <div key={entry.id} className="pricing-row">
                  <strong>{selectedCustomer?.name ?? 'Customer'}</strong>
                  <span>{productNameMap.get(entry.product_id) ?? `Product ${entry.product_id}`}</span>
                  <span className="price">¥{entry.override_price.toFixed(2)}</span>
                </div>
              ))
            ) : (
              <p className="table-placeholder">No pricing overrides recorded yet.</p>
            )}
          </div>
          <form className="panel-form" onSubmit={handlePurchaseSubmit}>
            <h4>Purchase entry</h4>
            <label>
              Product
              <select
                value={purchaseProductId}
                onChange={(event) => {
                  const value = event.target.value
                  setPurchaseProductId(value ? Number(value) : '')
                }}
              >
                <option value="">商品を選択</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.internal_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Purchase price
              <input
                value={purchaseValue}
                onChange={(event) => setPurchaseValue(event.target.value)}
                placeholder="¥58.00"
              />
            </label>
            <button type="submit">Record purchase</button>
            {purchaseMessage && <p className="status-message">{purchaseMessage}</p>}
          </form>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>PDF generation</h2>
            <p>Render packing slips, delivery notes, and invoices from the confirmed order.</p>
          </div>
          <div className="pdf-list">
            {pdfDeliverables.map((document) => (
              <div key={document.title} className="pdf-item">
                <strong>{document.title}</strong>
                <p>{document.detail}</p>
              </div>
            ))}
          </div>
          <div className="ocr-controls">
            {pdfDocumentTypes.map((document) => (
              <button
                type="button"
                key={document.value}
                onClick={() => handlePdfRender(document.value as 'packing' | 'delivery' | 'invoice')}
              >
                Generate {document.label}
              </button>
            ))}
          </div>
          {pdfMessage && (
            <p className="status-message">
              {pdfMessage}
              {pdfPreviewUrl && (
                <>
                  {' '}
                  <a href={pdfPreviewUrl} target="_blank" rel="noreferrer">
                    Preview URL
                  </a>
                </>
              )}
            </p>
          )}
        </article>
      </section>

      <section className="notes">
        <h2>Non-functional focus</h2>
        <ul>
          {nonFunctionalFocus.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </div>
  )
}

export default App
