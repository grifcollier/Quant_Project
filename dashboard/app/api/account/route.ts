import { NextResponse } from 'next/server';
import { getAccount } from '@/lib/alpaca';

export async function GET() {
  try {
    return NextResponse.json(await getAccount());
  } catch (e: unknown) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
