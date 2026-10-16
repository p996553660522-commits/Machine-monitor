#pragma once

// Plain IPv4 or ASCII DNS hostname. No URL, port, path or HTML characters.
// Kept independent of Arduino so the same validator has compile-time tests.
constexpr bool validMqttBrokerAddress(const char* host)
{
  if (!host || !host[0]) return false;
  unsigned length = 0, label = 0, dots = 0;
  bool numeric = true;
  char previous = 0;
  for (const char* p = host; *p; ++p)
  {
    const char c = *p;
    if (++length > 253) return false;
    if (c == '.')
    {
      if (!label || previous == '-') return false;
      label = 0;
      ++dots;
    }
    else
    {
      const bool digit = c >= '0' && c <= '9';
      const bool letter = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
      if (!digit && !letter && c != '-') return false;
      if (!label && c == '-') return false;
      if (++label > 63) return false;
      if (!digit) numeric = false;
    }
    previous = c;
  }
  if (!label || previous == '-') return false;
  if (!numeric) return true;
  if (dots != 3) return false;
  unsigned octet = 0, sum = 0;
  for (const char* p = host; ; ++p)
  {
    if (*p == '.' || !*p)
    {
      sum += octet;
      if (!*p) break;
      octet = 0;
    }
    else
    {
      octet = octet * 10 + (*p - '0');
      if (octet > 255) return false;
    }
  }
  return sum != 0;
}
