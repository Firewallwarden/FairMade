export const fieldValue = (form: FormData, name: string) =>
  String(form.get(name) ?? '').trim()
