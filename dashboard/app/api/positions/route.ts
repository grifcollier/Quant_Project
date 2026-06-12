import { NextResponse } from 'next/server';
import { getPositions } from '@/lib/alpaca';

export async function GET() {
  try {
    return NextResponse.json(await getPositions());
  } catch (e: unknown) {
    return NextResponse.json({ error: (e as Error).message }, { status: 502 });
  }
}
