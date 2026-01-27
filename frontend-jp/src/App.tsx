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
    title: '注文受付',
    description:
      'FAXをアップロードしてOCRテキストを抽出し、確認用のリストとして表示します。',
    outcome: '人が確認する販売オーダー行',
    label: '01',
  },
  {
    title: '商品マスター',
    description:
      'OCRの名称と内部SKUを紐づけ、未知名称をエイリアスとして記録します。',
    outcome: '整合した名称と価格',
    label: '02',
  },
  {
    title: '顧客と価格',
    description:
      '顧客ごとの価格差を記録し、次回以降に自動で反映させます。',
    outcome: '正確な請求情報',
    label: '03',
  },
  {
    title: '仕入れデータ',
    description:
      '手動で仕入価格を記録して基準価格を更新し、OCRのノイズを補正します。',
    outcome: '最新の原価履歴',
    label: '04',
  },
  {
    title: 'PDF出力',
    description:
      'テンプレートから現品票・納品書・請求書をHTML→PDFで生成します。',
    outcome: '印刷準備済みの書類',
    label: '05',
  },
]

const pdfDeliverables = [
  {
    title: '現品票（Packing Slip）',
    detail: '納品番号・ユニット・製品名・数量を含むPDFを明細単位で生成します。',
  },
  {
    title: '納品書（Delivery Note）',
    detail: '納品数量と現品票の対応をまとめたPDFを出力します。',
  },
  {
    title: '請求書（Invoice）',
    detail: '単価と合計を含む顧客向け請求書を生成します。',
  },
]

const quickStats = [
  { label: '人による確認', value: '100% 必須', detail: 'OCRは自動承認されません' },
  { label: '手入力削減', value: '70～80%', detail: '200行規模のFAXでも再入力を大幅削減' },
  { label: 'ユーザー', value: '1～3名', detail: 'デスクトップ専用・日本語UI' },
]

const nonFunctionalFocus = [
  '単一ロールログイン＋手動バックアップ/エクスポート',
  '動作を安定させて予測しやすく',
  'SQLite→PostgreSQL/RDS移行可能なスキーマ',
  'オフィスPC向けのレイアウト（モバイルなし）',
  '在庫や会計との連携は今後の拡張として除外',
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
  const [orderMessage, setOrderMessage] = useState('FAX PDFをアップロードしてワークフローを開始してください。')
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
      setOrderMessage('行の読み込みに失敗しました。再度お試しください。')
      setUploadError(error instanceof Error ? error.message : '行の読み込みに失敗しました。')
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
    setOrderMessage('アップロード中です...OCR結果を取得しています。')
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
      setOrderMessage('OCRプレビューが準備できました。確認して保存してください。')
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'アップロードに失敗しました。')
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
        <span className="hero-tag">FAX注文自動化MVP</span>
        <h1>FAX注文を確認済みのデジタルワークフローへ</h1>
        <p className="hero-subtitle">
          FAX PDFをアップロードし、OCR結果を確認・補正して、現品票・納品書・請求書を安定的に出力します。
        </p>
        <div className="hero-actions">
          <button type="button">注文受付を開始</button>
          <button type="button" className="ghost">
            PDFテンプレートを見る
          </button>
        </div>
        <div className="hero-meta">
          <span>フロントエンド: React + TypeScript</span>
          <span>バックエンド: Python 3.10+ + FastAPI（AWS準備済み）</span>
          <span>OCR: Google Cloud Vision API経由</span>
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
            <h2>注文受付</h2>
            <p>FAX PDFを顧客と紐づけてアップロードし、OCR結果を確認してください。</p>
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
                {uploading ? 'アップロード中...' : 'OCR結果を確認'}
              </button>
              <button type="button" className="ghost" disabled>
                販売オーダーとして確定
              </button>
            </div>
          </form>
          {uploadError && <p className="status-message error">{uploadError}</p>}
          <p className="status-message">{orderMessage}</p>
          {orderId && <p className="order-id">オーダーID: {orderId}</p>}
          {loadingLines ? (
            <p className="status-message">OCR行を読み込んでいます...</p>
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
            <p className="table-placeholder">まだ行がありません。PDFをアップロードしてください。</p>
          )}
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>商品マスター</h2>
            <p>顧客名称と内部SKUを紐づけ、エイリアス履歴を保持します。</p>
          </div>
          <form className="panel-form" onSubmit={handleAliasSubmit}>
            <label>
              内部商品
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
              エイリアス登録
              <input
                value={aliasName}
                onChange={(event) => setAliasName(event.target.value)}
                placeholder="顧客語彙（ウイングナットなど）"
              />
            </label>
            <button type="submit">エイリアスを登録</button>
          </form>
          {aliasError && <p className="status-message error">{aliasError}</p>}
          <div className="alias-list">
            <h4>登録済みエイリアス</h4>
            {aliasList.length ? (
              aliasList.map((alias) => (
                <div key={alias.id} className="alias-row">
                  <span>{productNameMap.get(alias.product_id) ?? `ID ${alias.product_id}`}</span>
                  <span>{alias.alias_name}</span>
                </div>
              ))
            ) : (
              <p>まだエイリアスがありません。</p>
            )}
          </div>
        </article>
      </section>

      <section className="panel-grid-two">
        <article className="panel">
          <div className="panel-heading">
            <h2>顧客と価格</h2>
            <p>価格オーバーライドや仕入れを記録し、請求書と基準価格を整えます。</p>
          </div>
          <form className="panel-form" onSubmit={handlePricingSubmit}>
            <label>
              顧客
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
              商品
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
              オーバーライド価格
              <input
                value={pricingValue}
                onChange={(event) => setPricingValue(event.target.value)}
                placeholder="¥62.00"
              />
            </label>
            <button type="submit">価格を保存</button>
            {pricingError && <p className="status-message error">{pricingError}</p>}
          </form>
          <div className="pricing-grid">
            {pricingOverrides.length ? (
              pricingOverrides.map((entry) => (
                <div key={entry.id} className="pricing-row">
                  <strong>{selectedCustomer?.name ?? '顧客'}</strong>
                  <span>{productNameMap.get(entry.product_id) ?? `商品 ${entry.product_id}`}</span>
                  <span className="price">¥{entry.override_price.toFixed(2)}</span>
                </div>
              ))
            ) : (
              <p className="table-placeholder">まだ価格オーバーライドがありません。</p>
            )}
          </div>
          <form className="panel-form" onSubmit={handlePurchaseSubmit}>
            <h4>仕入れ記録</h4>
            <label>
              商品
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
              仕入れ価格
              <input
                value={purchaseValue}
                onChange={(event) => setPurchaseValue(event.target.value)}
                placeholder="¥58.00"
              />
            </label>
            <button type="submit">仕入れを記録</button>
            {purchaseMessage && <p className="status-message">{purchaseMessage}</p>}
          </form>
        </article>

        <article className="panel">
          <div className="panel-heading">
            <h2>PDF出力</h2>
            <p>確定済みオーダーから現品票・納品書・請求書を生成します。</p>
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
                {document.label} を生成
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
