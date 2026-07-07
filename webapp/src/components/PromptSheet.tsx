import { useEffect, useState } from "react";
import { Button, Drawer, Stack, TextInput } from "@mantine/core";
import { useTranslation } from "react-i18next";

export function PromptSheet({
  title, label, placeholder, password, submitText, open, onSubmit, onClose,
}: {
  title: string;
  label?: string;
  placeholder?: string;
  password?: boolean;
  submitText?: string;
  open: boolean;
  onSubmit: (value: string) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [value, setValue] = useState("");

  useEffect(() => {
    if (!open) setValue("");
  }, [open]);

  return (
    <Drawer
      opened={open}
      onClose={onClose}
      title={title}
      position="bottom"
      radius="lg"
      overlayProps={{ blur: 2 }}
    >
      <Stack gap={8} pb={16} px={4}>
        <TextInput
          label={label}
          type={password ? "password" : "text"}
          placeholder={placeholder}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && value.trim() && onSubmit(value.trim())}
          autoFocus
        />
        <Button
          fullWidth
          disabled={!value.trim()}
          onClick={() => onSubmit(value.trim())}
        >
          {submitText ?? t("btn_save")}
        </Button>
        <Button fullWidth variant="default" onClick={onClose}>
          {t("btn_cancel")}
        </Button>
      </Stack>
    </Drawer>
  );
}
