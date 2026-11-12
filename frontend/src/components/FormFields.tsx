import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react'

export function Field({
  title,
  name,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { title: string; name: string }) {
  return (
    <label className="calculator-field" htmlFor={name}>
      {title}
      <input id={name} name={name} {...props} />
    </label>
  )
}

export function TextArea({
  title,
  name,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  title: string
  name: string
}) {
  return (
    <label className="calculator-field" htmlFor={name}>
      {title}
      <textarea id={name} name={name} rows={4} {...props} />
    </label>
  )
}
