import { useState } from 'react'
import { RefundRequestList } from './RefundRequestList'
import { getSellerRefundRequests } from '../services/seller-refund-list'

export function SellerRefundInbox() {
  const [open, setOpen] = useState(false)
  return <>
    <button className="calculator-secondary" aria-expanded={open} onClick={() => setOpen(!open)}>Seller refund inbox</button>
    {open && <RefundRequestList title="Seller refund inbox" loadPage={getSellerRefundRequests} orderPath="seller-orders" />}
  </>
}
