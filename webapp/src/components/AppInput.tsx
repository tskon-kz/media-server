import {TextInput, type TextInputProps} from "@mantine/core"
import styles from "./AppInput.module.scss"

export function AppInput(props: TextInputProps) {
  return (
    <TextInput
      {...props}
      classNames={{
        input: styles.input,
        ...props.classNames,
      }}
    />
  )
}
