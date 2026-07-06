import { type ReactNode, Children, Fragment } from "react";
import {
  Box, Center, Divider, Stack, Text, Title,
  UnstyledButton, type BoxProps,
} from "@mantine/core";

// ── ListSection ──────────────────────────────────────────────────────────────

interface ListSectionProps {
  header?: string;
  footer?: string;
  children?: ReactNode;
  style?: React.CSSProperties;
}

export function ListSection({ header, footer, children, style }: ListSectionProps) {
  const items = Children.toArray(children);
  return (
    <Box mb={8} style={style}>
      {header && (
        <Text size="xs" c="dimmed" tt="uppercase" fw={500} px={16} pb={6}>
          {header}
        </Text>
      )}
      {items.length > 0 && (
        <Box
          style={{
            background: "var(--tg-theme-section-bg-color)",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          {items.map((child, i) => (
            <Fragment key={i}>
              {i > 0 && <Divider ml={16} style={{ borderColor: "rgba(128,128,128,0.15)" }} />}
              {child}
            </Fragment>
          ))}
        </Box>
      )}
      {footer && (
        <Text size="xs" c="dimmed" px={16} pt={6}>
          {footer}
        </Text>
      )}
    </Box>
  );
}

// ── ListItem ─────────────────────────────────────────────────────────────────

interface ListItemProps extends BoxProps {
  before?: ReactNode;
  after?: ReactNode;
  subtitle?: ReactNode;
  description?: ReactNode;
  onClick?: () => void;
  multiline?: boolean;
  children: ReactNode;
}

export function ListItem({
  before, after, subtitle, description, onClick, multiline, children, style, ...rest
}: ListItemProps) {
  const content = (
    <Box
      style={{
        display: "flex",
        alignItems: before || after ? "center" : undefined,
        gap: 12,
        padding: "12px 16px",
        width: "100%",
        minHeight: 44,
        ...style,
      }}
      {...rest}
    >
      {before && (
        <Box style={{ flexShrink: 0, color: "var(--tg-theme-hint-color)" }}>
          {before}
        </Box>
      )}
      <Box style={{ flex: 1, minWidth: 0 }}>
        <Text
          size="md"
          style={{ color: "var(--tg-theme-text-color)", whiteSpace: multiline ? "normal" : "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
        >
          {children}
        </Text>
        {subtitle && (
          <Text size="sm" c="dimmed" style={{ whiteSpace: multiline ? "normal" : "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {subtitle}
          </Text>
        )}
        {description}
      </Box>
      {after && (
        <Box style={{ flexShrink: 0, marginLeft: "auto", color: "var(--tg-theme-hint-color)" }}>
          {after}
        </Box>
      )}
    </Box>
  );

  if (onClick) {
    return (
      <UnstyledButton
        onClick={onClick}
        style={{ width: "100%", display: "block" }}
        styles={{ root: { "&:hover": { background: "rgba(128,128,128,0.06)" } } }}
      >
        {content}
      </UnstyledButton>
    );
  }

  return content;
}

// ── ListPlaceholder ───────────────────────────────────────────────────────────

export function ListPlaceholder({
  header, description,
}: { header?: string; description?: string }) {
  return (
    <Center py={60}>
      <Stack align="center" gap={8}>
        {header && (
          <Title order={4} style={{ color: "var(--tg-theme-text-color)" }}>
            {header}
          </Title>
        )}
        {description && (
          <Text c="dimmed" ta="center" size="sm" maw={280}>
            {description}
          </Text>
        )}
      </Stack>
    </Center>
  );
}
