import { cloneElement, useId } from 'react'

// Nhãn + ô nhập: tự sinh id để nhãn gắn đúng với ô (trình đọc màn hình đọc được tên ô)
export default function Field({ label, small = false, className = '', children }) {
  const id = useId()
  return (
    <div className={`form-group ${className}`.trim()}>
      <label htmlFor={id} className={`form-label${small ? ' form-label-sm' : ''}`}>
        {label}
      </label>
      {cloneElement(children, { id })}
    </div>
  )
}
